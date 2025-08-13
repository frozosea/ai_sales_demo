#!/usr/bin/env python3
"""
Ручной e2e-бенч TTS (HTTP+WS): короткие/длинные фразы, TTFT, handshake, устойчивость
"""

import asyncio
import time
import json
import logging
import argparse
import statistics
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv

from tts_manager.config import load_tts_config
from tts_manager.connection_pool import TTSConnectionPool, ConnectionType
from tts_manager.manager import TTSManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("tts_bench")

def jlog(event: str, **kwargs):
    """Логирование в JSON формате"""
    log.info(json.dumps({"event": event, **kwargs}, ensure_ascii=False))


class TTSBenchmark:
    """Класс для проведения бенчмарка TTS"""
    
    def __init__(self, config_path: str, output_dir: str, repeats: int = 3):
        self.config_path = config_path
        self.output_dir = Path(output_dir)
        self.repeats = repeats
        self.cfg = None
        self.connection_pool = None
        
        # Результаты тестов
        self.results = {
            "ws_short": {"handshake_ms": [], "ttft_ms": [], "total_ms": [], "connection_latency_ms": [], "streaming_latency_ms": []},
            "ws_long": {"handshake_ms": [], "ttft_ms": [], "total_ms": [], "connection_latency_ms": [], "streaming_latency_ms": []},
            "http_short": {"connection_ms": [], "ttfa_ms": [], "total_ms": [], "connection_latency_ms": [], "streaming_latency_ms": [], "request_send_ms": [], "response_time_ms": [], "network_ops_ms": []},
            "http_long": {"connection_ms": [], "ttfa_ms": [], "total_ms": [], "connection_latency_ms": [], "streaming_latency_ms": [], "request_send_ms": [], "response_time_ms": [], "network_ops_ms": []}
        }
        
        # Создаем директорию для отчетов
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def setup(self):
        """Инициализация конфигурации и пула соединений"""
        jlog("bench_setup_start", config_path=self.config_path)
        
        # Загружаем переменные окружения
        load_dotenv(override=False)
        jlog("env_loaded", api_key_length=len(os.getenv("ELEVEN_API_KEY", "")), 
             voice_id=os.getenv("ELEVEN_VOICE_ID", ""), 
             model_id=os.getenv("ELEVEN_MODEL_ID", ""))
        
        # Загружаем конфигурацию
        self.cfg = load_tts_config(self.config_path)
        
        # Создаем пул соединений с настройками для бенчмарка
        self.connection_pool = TTSConnectionPool(
            self.cfg,
            max_connections=10,
            max_idle_time=300.0,
            cleanup_interval=60.0,
            enable_retry=True,
            retry_attempts=3,
            enable_connection_pooling=True,
            enable_keep_alive=True,
            enable_warming=True,
            warming_threshold=30.0,
            proxy_url="http://127.0.0.1:10807"  # Используем прокси для обхода ограничений
        )
        
        await self.connection_pool.start()
        jlog("bench_setup_complete")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        if self.connection_pool:
            await self.connection_pool.close()
        jlog("bench_cleanup_complete")
    
    async def run_ws_case(self, text: str, case_name: str) -> Dict[str, List[float]]:
        """Запуск WebSocket теста"""
        jlog("ws_case_start", case_name=case_name, text_length=len(text), repeats=self.repeats)
        
        results = {"handshake_ms": [], "ttft_ms": [], "total_ms": [], "connection_latency_ms": [], "streaming_latency_ms": []}
        
        for i in range(self.repeats):
            jlog("ws_iteration_start", case_name=case_name, iteration=i + 1, total=self.repeats)
            
            try:
                # Создаем менеджер для этого звонка
                call_id = f"{case_name}_{i + 1}"
                tts_mgr = TTSManager(self.cfg, self.connection_pool, call_id)
                
                # Измеряем handshake
                handshake_start = time.perf_counter()
                websocket = await self.connection_pool.get_websocket_connection(call_id)
                handshake_ms = (time.perf_counter() - handshake_start) * 1000
                jlog("ws_handshake_finish", ms=round(handshake_ms, 2), call_id=call_id)
            
                # Запускаем LLM стрим
                text_q, audio_q = await tts_mgr.start_llm_stream()
                
                # Отправляем текст и измеряем TTFT
                send_start = time.perf_counter()
                await text_q.put(text)
                
                # Читаем аудио и измеряем метрики
                first_audio_time = None
                total_bytes = 0
                chunks_count = 0
                
                while True:
                    audio_chunk = await audio_q.get()
                    if audio_chunk is None:  # Конец стрима
                        break
                    
                    if first_audio_time is None:
                        first_audio_time = (time.perf_counter() - send_start) * 1000
                        jlog("ws_first_audio", ms=round(first_audio_time, 2), bytes=len(audio_chunk), call_id=call_id)
                    
                    total_bytes += len(audio_chunk)
                    chunks_count += 1
                
                total_ms = (time.perf_counter() - send_start) * 1000
                jlog("ws_stream_end", total_ms=round(total_ms, 2), chunks=chunks_count, bytes=total_bytes, call_id=call_id)
                
                # Освобождаем соединение
                await self.connection_pool.release_connection(call_id, ConnectionType.WEBSOCKET)
                
                # Вычисляем различные типы задержек
                connection_latency = handshake_ms  # Чистое время handshake (гео-влияние)
                streaming_latency = first_audio_time or total_ms  # Время стриминга (серверная производительность)
                
                # Сохраняем результаты
                results["handshake_ms"].append(handshake_ms)
                results["ttft_ms"].append(first_audio_time or total_ms)
                results["total_ms"].append(total_ms)
                results["connection_latency_ms"].append(connection_latency)
                results["streaming_latency_ms"].append(streaming_latency)
                
                jlog("ws_iteration_complete", case_name=case_name, iteration=i + 1, 
                     handshake_ms=round(handshake_ms, 2), ttft_ms=round(first_audio_time or total_ms, 2),
                     connection_latency_ms=round(connection_latency, 2), streaming_latency_ms=round(streaming_latency, 2))
                     
            except Exception as e:
                jlog("ws_iteration_error", case_name=case_name, iteration=i + 1, error=str(e))
                # Добавляем пустые значения для статистики
                results["handshake_ms"].append(0.0)
                results["ttft_ms"].append(0.0)
                results["total_ms"].append(0.0)
                results["connection_latency_ms"].append(0.0)
                results["streaming_latency_ms"].append(0.0)
        
        jlog("ws_case_complete", case_name=case_name, 
             avg_handshake=round(statistics.mean(results["handshake_ms"]), 2),
             avg_ttft=round(statistics.mean(results["ttft_ms"]), 2),
             avg_connection_latency=round(statistics.mean(results["connection_latency_ms"]), 2),
             avg_streaming_latency=round(statistics.mean(results["streaming_latency_ms"]), 2))
        
        return results
    
    async def run_http_case(self, text: str, case_name: str) -> Dict[str, List[float]]:
        """Запуск HTTP теста"""
        jlog("http_case_start", case_name=case_name, text_length=len(text), repeats=self.repeats)
        
        results = {
            "connection_ms": [], "ttfa_ms": [], "total_ms": [], 
            "connection_latency_ms": [], "streaming_latency_ms": [],
            "request_send_ms": [], "response_time_ms": [], "network_ops_ms": []
        }
        
        for i in range(self.repeats):
            jlog("http_iteration_start", case_name=case_name, iteration=i + 1, total=self.repeats)
            
            try:
                # Создаем менеджер для этого звонка
                call_id = f"{case_name}_{i + 1}"
                tts_mgr = TTSManager(self.cfg, self.connection_pool, call_id)
                
                # Измеряем время получения соединения
                connection_start = time.perf_counter()
                http_client = await self.connection_pool.get_http_connection(call_id)
                connection_ms = (time.perf_counter() - connection_start) * 1000
                jlog("http_connection_finish", ms=round(connection_ms, 2), call_id=call_id)
                
                # Измеряем время отправки запроса
                request_start = time.perf_counter()
                jlog("http_request_start", text_length=len(text), call_id=call_id)
                
                # Создаем менеджер и начинаем стрим
                tts_mgr = TTSManager(self.cfg, self.connection_pool, call_id)
                stream_generator = tts_mgr.stream_static_text(text)
                
                # Получаем первый чанк (это включает отправку запроса + получение ответа)
                first_chunk = await stream_generator.__anext__()
                request_send_ms = (time.perf_counter() - request_start) * 1000
                jlog("http_request_sent", ms=round(request_send_ms, 2), bytes=len(first_chunk), call_id=call_id)
                
                # Измеряем время до первого байта (response time)
                response_start = time.perf_counter()
                first_byte_time = request_send_ms  # Время до первого байта = время отправки запроса
                jlog("http_first_byte", ms=round(first_byte_time, 2), bytes=len(first_chunk), call_id=call_id)
                
                # Продолжаем стриминг
                total_bytes = len(first_chunk)
                chunks_count = 1
                
                try:
                    async for chunk in stream_generator:
                        total_bytes += len(chunk)
                        chunks_count += 1
                except StopAsyncIteration:
                    pass
                
                total_ms = (time.perf_counter() - request_start) * 1000
                jlog("http_stream_end", total_ms=round(total_ms, 2), chunks=chunks_count, bytes=total_bytes, call_id=call_id)
                
                # Освобождаем соединение
                await self.connection_pool.release_connection(call_id, ConnectionType.HTTP)
                
                # Вычисляем различные типы задержек
                connection_latency = connection_ms  # Чистое время соединения (гео-влияние)
                request_send_latency = request_send_ms  # Время отправки запроса
                response_time = first_byte_time  # Время до первого байта
                streaming_latency = total_ms - request_send_ms  # Время стриминга после первого байта
                network_ops = connection_ms + request_send_ms  # Общее время сетевых операций
                
                # Сохраняем результаты
                results["connection_ms"].append(connection_ms)
                results["ttfa_ms"].append(first_byte_time)
                results["total_ms"].append(total_ms)
                results["connection_latency_ms"].append(connection_latency)
                results["streaming_latency_ms"].append(streaming_latency)
                results["request_send_ms"].append(request_send_latency)
                results["response_time_ms"].append(response_time)
                results["network_ops_ms"].append(network_ops)
                
                jlog("http_iteration_complete", case_name=case_name, iteration=i + 1, 
                     connection_ms=round(connection_ms, 2), ttfa_ms=round(first_byte_time, 2),
                     connection_latency_ms=round(connection_latency, 2), streaming_latency_ms=round(streaming_latency, 2),
                     request_send_ms=round(request_send_latency, 2), response_time_ms=round(response_time, 2),
                     network_ops_ms=round(network_ops, 2))
                     
            except Exception as e:
                jlog("http_iteration_error", case_name=case_name, iteration=i + 1, error=str(e))
                # Добавляем пустые значения для статистики
                results["connection_ms"].append(0.0)
                results["ttfa_ms"].append(0.0)
                results["total_ms"].append(0.0)
                results["connection_latency_ms"].append(0.0)
                results["streaming_latency_ms"].append(0.0)
                results["request_send_ms"].append(0.0)
                results["response_time_ms"].append(0.0)
                results["network_ops_ms"].append(0.0)
        
        jlog("http_case_complete", case_name=case_name, 
             avg_connection=round(statistics.mean(results["connection_ms"]), 2),
             avg_ttfa=round(statistics.mean(results["ttfa_ms"]), 2),
             avg_connection_latency=round(statistics.mean(results["connection_latency_ms"]), 2),
             avg_streaming_latency=round(statistics.mean(results["streaming_latency_ms"]), 2),
             avg_request_send=round(statistics.mean(results["request_send_ms"]), 2),
             avg_response_time=round(statistics.mean(results["response_time_ms"]), 2),
             avg_network_ops=round(statistics.mean(results["network_ops_ms"]), 2))
        
        return results
    
    def calculate_statistics(self, data: List[float]) -> Dict[str, float]:
        """Вычисляет статистику для списка значений"""
        if not data:
            return {"avg": None, "p50": None, "p95": None, "min": None, "max": None}
        
        # Фильтруем нулевые значения (ошибки)
        valid_data = [x for x in data if x > 0]
        
        if not valid_data:
            return {"avg": None, "p50": None, "p95": None, "min": None, "max": None}
        
        try:
            return {
                "avg": round(statistics.mean(valid_data), 2),
                "p50": round(statistics.quantiles(valid_data, n=2)[0], 2),
                "p95": round(statistics.quantiles(valid_data, n=20)[18], 2) if len(valid_data) >= 20 else round(statistics.quantiles(valid_data, n=len(valid_data))[-1], 2),
                "min": round(min(valid_data), 2),
                "max": round(max(valid_data), 2)
            }
        except Exception:
            return {"avg": None, "p50": None, "p95": None, "min": None, "max": None}
    
    def generate_summary(self) -> Dict[str, Any]:
        """Генерирует сводку результатов"""
        summary = {}
        
        # Статистика для каждого случая
        for case_name, metrics in self.results.items():
            summary[case_name] = {}
            for metric_name, values in metrics.items():
                summary[case_name][metric_name] = self.calculate_statistics(values)
        
        # Целевые значения
        summary["goals"] = {
            "ttft_ms": 800,  # Цель для TTFT
            "ttfa_ms": 1000,  # Цель для TTFA
            "handshake_ms": 500  # Цель для handshake
        }
        
        # Общие выводы
        summary["conclusions"] = {
            "ws_ttft_meets_goal": all(
                summary["ws_short"]["ttft_ms"]["avg"] < summary["goals"]["ttft_ms"],
                summary["ws_long"]["ttft_ms"]["avg"] < summary["goals"]["ttft_ms"]
            ) if summary["ws_short"]["ttft_ms"]["avg"] and summary["ws_long"]["ttft_ms"]["avg"] else False,
            "http_ttfa_meets_goal": all(
                summary["http_short"]["ttfa_ms"]["avg"] < summary["goals"]["ttfa_ms"],
                summary["http_long"]["ttfa_ms"]["avg"] < summary["goals"]["ttfa_ms"]
            ) if summary["http_short"]["ttfa_ms"]["avg"] and summary["http_long"]["ttfa_ms"]["avg"] else False,
            "ws_handshake_meets_goal": all(
                summary["ws_short"]["handshake_ms"]["avg"] < summary["goals"]["handshake_ms"],
                summary["ws_long"]["handshake_ms"]["avg"] < summary["goals"]["handshake_ms"]
            ) if summary["ws_short"]["handshake_ms"]["avg"] and summary["ws_long"]["handshake_ms"]["avg"] else False
        }
        
        return summary
    
    def save_reports(self, summary: Dict[str, Any]):
        """Сохраняет отчеты в JSON и Markdown"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # JSON отчет
        json_path = self.output_dir / f"tts_summary_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # Markdown отчет
        md_path = self.output_dir / f"tts_summary_{timestamp}.md"
        md_content = self.generate_markdown_report(summary)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        jlog("report_saved", path_json=str(json_path), path_md=str(md_path))
    
    def generate_markdown_report(self, summary: Dict[str, Any]) -> str:
        """Генерирует Markdown отчет"""
        md = f"""# TTS Benchmark Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Goals
- **TTFT (WebSocket)**: < {summary['goals']['ttft_ms']} ms
- **TTFA (HTTP)**: < {summary['goals']['ttfa_ms']} ms  
- **Handshake (WebSocket)**: < {summary['goals']['handshake_ms']} ms
- **Network Latency**: < 2000 ms (estimated geo impact)

## Results Summary

### WebSocket - Short Text
| Metric | Avg | P50 | P95 | Min | Max |
|--------|-----|-----|-----|-----|-----|
"""
        
        for metric, stats in summary["ws_short"].items():
            md += f"| {metric} | {stats['avg'] or 'N/A'} | {stats['p50'] or 'N/A'} | {stats['p95'] or 'N/A'} | {stats['min'] or 'N/A'} | {stats['max'] or 'N/A'} |\n"
        
        md += "\n### WebSocket - Long Text\n| Metric | Avg | P50 | P95 | Min | Max |\n|--------|-----|-----|-----|-----|-----|\n"
        
        for metric, stats in summary["ws_long"].items():
            md += f"| {metric} | {stats['avg'] or 'N/A'} | {stats['p50'] or 'N/A'} | {stats['p95'] or 'N/A'} | {stats['min'] or 'N/A'} | {stats['max'] or 'N/A'} |\n"
        
        md += "\n### HTTP - Short Text\n| Metric | Avg | P50 | P95 | Min | Max |\n|--------|-----|-----|-----|-----|-----|\n"
        
        for metric, stats in summary["http_short"].items():
            md += f"| {metric} | {stats['avg'] or 'N/A'} | {stats['p50'] or 'N/A'} | {stats['p95'] or 'N/A'} | {stats['min'] or 'N/A'} | {stats['max'] or 'N/A'} |\n"
        
        md += "\n### HTTP - Long Text\n| Metric | Avg | P50 | P95 | Min | Max |\n|--------|-----|-----|-----|-----|-----|\n"
        
        for metric, stats in summary["http_long"].items():
            md += f"| {metric} | {stats['avg'] or 'N/A'} | {stats['p50'] or 'N/A'} | {stats['p95'] or 'N/A'} | {stats['min'] or 'N/A'} | {stats['max'] or 'N/A'} |\n"
        
        md += "\n## Network Analysis\n"
        # Анализ сетевых задержек
        ws_short_conn = summary["ws_short"]["connection_latency_ms"]["avg"]
        ws_long_conn = summary["ws_long"]["connection_latency_ms"]["avg"]
        ws_short_stream = summary["ws_short"]["streaming_latency_ms"]["avg"]
        ws_long_stream = summary["ws_long"]["streaming_latency_ms"]["avg"]
        
        http_short_conn = summary["http_short"]["connection_latency_ms"]["avg"]
        http_long_conn = summary["http_long"]["connection_latency_ms"]["avg"]
        http_short_stream = summary["http_short"]["streaming_latency_ms"]["avg"]
        http_long_stream = summary["http_long"]["streaming_latency_ms"]["avg"]
        
        if http_short_conn and http_long_conn and http_short_stream and http_long_stream:
            avg_http_conn = (http_short_conn + http_long_conn) / 2
            avg_http_stream = (http_short_stream + http_long_stream) / 2
            md += f"- **HTTP Connection Latency (Geo Impact)**: {avg_http_conn:.1f} ms\n"
            md += f"- **HTTP Streaming Latency (Server Performance)**: {avg_http_stream:.1f} ms\n"
            md += f"- **HTTP Total Network Latency**: {avg_http_conn + avg_http_stream:.1f} ms\n"
        
        if ws_short_conn and ws_long_conn and ws_short_stream and ws_long_stream:
            avg_ws_conn = (ws_short_conn + ws_long_conn) / 2
            avg_ws_stream = (ws_short_stream + ws_long_stream) / 2
            md += f"- **WebSocket Connection Latency (Geo Impact)**: {avg_ws_conn:.1f} ms\n"
            md += f"- **WebSocket Streaming Latency (Server Performance)**: {avg_ws_stream:.1f} ms\n"
            md += f"- **WebSocket Total Network Latency**: {avg_ws_conn + avg_ws_stream:.1f} ms\n"
        
        # Оценка серверной производительности
        if http_short_stream and http_long_stream:
            md += f"\n### Server Performance Estimates\n"
            md += f"- **Server-side TTFA (HTTP)**: ~{avg_http_stream - 100:.0f} ms\n"
            md += f"- **Server-side TTFT (WebSocket)**: ~{avg_ws_stream - 100:.0f} ms (if working)\n"
            md += f"- **Geo Impact**: ~{avg_http_conn:.0f} ms\n"
        
        md += "\n## Conclusions\n"
        conclusions = summary["conclusions"]
        md += f"- **TTFT meets goal**: {'✅' if conclusions['ws_ttft_meets_goal'] else '❌'}\n"
        md += f"- **TTFA meets goal**: {'✅' if conclusions['http_ttfa_meets_goal'] else '❌'}\n"
        md += f"- **Handshake meets goal**: {'✅' if conclusions['ws_handshake_meets_goal'] else '❌'}\n"
        
        return md
    
    async def run_benchmark(self, ws_short_text: str, ws_long_text: str, 
                           http_short_text: str, http_long_text: str):
        """Запуск полного бенчмарка"""
        jlog("benchmark_start", repeats=self.repeats)
        
        try:
            await self.setup()
            
            # WebSocket тесты
            self.results["ws_short"] = await self.run_ws_case(ws_short_text, "ws_short")
            self.results["ws_long"] = await self.run_ws_case(ws_long_text, "ws_long")
            
            # HTTP тесты
            self.results["http_short"] = await self.run_http_case(http_short_text, "http_short")
            self.results["http_long"] = await self.run_http_case(http_long_text, "http_long")
            
            # Генерируем и сохраняем отчеты
            summary = self.generate_summary()
            self.save_reports(summary)
            
            jlog("benchmark_complete")
            
        finally:
            await self.cleanup()


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="TTS E2E Benchmark")
    parser.add_argument("--config", default="configs/tts_config.yml", help="Path to TTS config")
    parser.add_argument("--repeats", type=int, default=3, help="Number of test repetitions")
    parser.add_argument("--out", default="reports", help="Output directory for reports")
    parser.add_argument("--ws-chunk", default="Стоимость 12000 рублей.", help="Short text for WebSocket test")
    parser.add_argument("--ws-long", 
                       default="Это длинная проверочная реплика для тестирования производительности системы преобразования текста в речь. Она содержит более трехсот символов и включает в себя различные элементы: числа (например, 12345), пунктуацию (точки, запятые, восклицательные знаки!), а также разнообразные слова для проверки качества синтеза речи на русском языке. Такие длинные фразы позволяют оценить стабильность работы системы и качество генерации аудио при обработке больших объемов текста.",
                       help="Long text for WebSocket test")
    parser.add_argument("--http-chunk", default="Стоимость 12000 рублей.", help="Short text for HTTP test")
    parser.add_argument("--http-long",
                       default="Это длинная проверочная реплика для тестирования производительности системы преобразования текста в речь. Она содержит более трехсот символов и включает в себя различные элементы: числа (например, 12345), пунктуацию (точки, запятые, восклицательные знаки!), а также разнообразные слова для проверки качества синтеза речи на русском языке. Такие длинные фразы позволяют оценить стабильность работы системы и качество генерации аудио при обработке больших объемов текста.",
                       help="Long text for HTTP test")
    
    args = parser.parse_args()
    
    # Создаем и запускаем бенчмарк
    benchmark = TTSBenchmark(args.config, args.out, args.repeats)
    await benchmark.run_benchmark(
        args.ws_chunk, args.ws_long, 
        args.http_chunk, args.http_long
    )


if __name__ == "__main__":
    asyncio.run(main())

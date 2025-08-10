import argparse
import os
from grpc_tools import protoc

def generate_stubs(src_dir, out_dir):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    proto_files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith('.proto')]
    if not proto_files:
        print(f"No .proto files found in {src_dir}")
        return

    proto_path = [
        f'-I{src_dir}',
        '-Ithird_party/googleapis',
        '-Ithird_party/yandex-cloud-api',
        '-Ithird_party/googleapis/google',
        '-Ithird_party/googleapis/google/api',
        '-Ithird_party/yandex-cloud-api/yandex/cloud'
    ]
    
    command = [
        'grpc_tools.protoc',
    ] + proto_path + [
        f'--python_out={out_dir}',
        f'--grpc_python_out={out_dir}',
    ] + proto_files

    print(f"Running command: {' '.join(command)}")
    if protoc.main(command) != 0:
        print("Error: gRPC stub generation failed.")
    else:
        print("Successfully generated gRPC stubs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate gRPC stubs for Yandex SpeechKit v3.")
    parser.add_argument("--src", default="third_party/speechkit_stt_v3", help="Source directory with .proto files.")
    parser.add_argument("--out", default="third_party/speechkit_stt_v3", help="Output directory for generated stubs.")
    args = parser.parse_args()
    generate_stubs(args.src, args.out) 
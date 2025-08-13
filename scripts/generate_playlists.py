import json
import re

def generate_playlists(dialogue_flow: dict) -> dict:
    """
    Generates playlists for system responses in the dialogue flow.
    """
    for state_name, state_data in dialogue_flow.items():
        system_response = state_data.get("system_response", {})
        
        if "template" in system_response and "playlist" not in system_response:
            template = system_response["template"]
            
            # Find all variables like {{ ... }}
            variables = re.findall(r"(\{\{.*?\}\})", template)
            
            if not variables:
                # No variables, simple cache entry
                system_response["playlist"] = [
                    {
                        "type": "cache",
                        "key": system_response.get("redis_key", f"static:{state_name}")
                    }
                ]
            else:
                # Split text by variables to get static parts
                static_parts = re.split(r"\{\{.*?\}\}", template)
                playlist = []
                
                for i, static_part in enumerate(static_parts):
                    if static_part:
                        # Add static part as a cache entry
                        playlist.append({
                            "type": "cache",
                            "key": f"static:{state_name}_part_{i}"
                        })
                    
                    if i < len(variables):
                        # Add the variable part as a TTS entry
                        playlist.append({
                            "type": "tts",
                            "text_template": variables[i]
                        })
                
                system_response["playlist"] = playlist
    
    return dialogue_flow

if __name__ == "__main__":
    with open("configs/dialogue_flow.json", "r", encoding="utf-8") as f:
        dialogue_data = json.load(f)
    
    updated_dialogue_data = generate_playlists(dialogue_data)
    
    with open("configs/dialogue_flow_with_playlists.json", "w", encoding="utf-8") as f:
        json.dump(updated_dialogue_data, f, ensure_ascii=False, indent=2)
        
    print("Successfully generated playlists in 'configs/dialogue_flow_with_playlists.json'")

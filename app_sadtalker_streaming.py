#!/usr/bin/env python3
"""
Enhanced SadTalker with Real-time Streaming Support
Uses Fast Preview Mode for immediate visual feedback
"""

import os
import sys
import gradio as gr
import asyncio
import websockets
import json
import base64
import cv2
import numpy as np
import threading
import time
from src.gradio_demo import SadTalker  
from src.facerender.animate_fast_preview import FastPreviewGenerator

try:
    import webui  # in webui
    in_webui = True
except:
    in_webui = False

class StreamingSadTalker:
    def __init__(self, checkpoint_path='checkpoints', config_path='src/config'):
        self.sad_talker = SadTalker(checkpoint_path, config_path, lazy_load=True)
        self.fast_preview = None
        self.streaming_clients = set()
        self.current_frame = None
        self.streaming_state = {"active": False, "progress": 0, "status": "Ready"}
        self.sadtalker_paths = None
        
    def setup_fast_preview(self, size=256, preprocess='crop'):
        """Initialize fast preview generator"""
        if self.fast_preview is None:
            # Initialize sadtalker_paths if not already done
            if self.sadtalker_paths is None:
                from src.utils.init_path import init_path
                self.sadtalker_paths = init_path(self.sad_talker.checkpoint_path, self.sad_talker.config_path, size, False, preprocess)
            
            self.fast_preview = FastPreviewGenerator(
                self.sadtalker_paths, 
                self.sad_talker.device, 
                preview_size=128
            )
    
    def frame_to_base64(self, frame):
        """Convert frame to base64 for WebSocket transmission"""
        if frame is None:
            return None
        
        # Convert tensor to numpy if needed
        if hasattr(frame, 'cpu'):
            frame = frame.cpu()
        if hasattr(frame, 'numpy'):
            frame = frame.numpy()
        
        # Handle batch dimension
        if len(frame.shape) == 4:
            frame = frame[0]
        
        # Convert to uint8 and transpose
        frame = np.transpose(frame, (1, 2, 0))
        frame = (frame * 255).astype(np.uint8)
        
        # Convert to base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        return frame_base64
    
    def broadcast_frame(self, frame_data):
        """Broadcast frame to all connected WebSocket clients"""
        if not self.streaming_clients:
            return
        
        try:
            frame_base64 = self.frame_to_base64(frame_data['frame'])
            if frame_base64 is None:
                return
            
            message = {
                'type': 'frame_update',
                'frame': frame_base64,
                'frame_idx': frame_data['frame_idx'],
                'progress': frame_data['progress'],
                'total_frames': frame_data['total_frames'],
                'status': frame_data.get('status', 'Processing'),
                'is_nodding': frame_data.get('is_nodding', False),
                'is_preview': frame_data.get('is_preview', False),
                'resolution': frame_data.get('resolution', 256)
            }
            
            # Broadcast to all clients
            for client in list(self.streaming_clients):
                try:
                    asyncio.create_task(client.send(json.dumps(message)))
                except:
                    self.streaming_clients.discard(client)
                    
        except Exception as e:
            print(f"Error broadcasting frame: {e}")
    
    def generate_with_streaming(self, source_image, driven_audio, preprocess_type, is_still_mode, 
                               enhancer, batch_size, size_of_image, pose_style):
        """Generate video with real-time streaming preview"""
        
        self.streaming_state["active"] = True
        self.streaming_state["status"] = "Initializing..."
        
        try:
            # Setup fast preview with proper initialization
            self.setup_fast_preview(int(size_of_image), preprocess_type)
            
            # Start nodding animation
            self.streaming_state["status"] = "Avatar is ready... nodding while processing"
            
            # Generate fast preview frames
            result_path = self.sad_talker.test_streaming(
                source_image=source_image,
                driven_audio=driven_audio,
                preprocess=preprocess_type,
                still_mode=is_still_mode,
                use_enhancer=enhancer,
                batch_size=int(batch_size),
                size=int(size_of_image),
                pose_style=int(pose_style),
                callback=self.broadcast_frame
            )
            
            self.streaming_state["active"] = False
            self.streaming_state["status"] = "Generation complete!"
            
            return result_path, self.current_frame.png() if self.current_frame is not None else None, self.streaming_state["status"]
            
        except Exception as e:
            self.streaming_state["active"] = False
            self.streaming_state["status"] = f"Error: {str(e)}"
            print(f"Error in generate_with_streaming: {e}")
            import traceback
            traceback.print_exc()
            return None, None, self.streaming_state["status"]

def toggle_audio_file(choice):
    if choice == False:
        return gr.update(visible=True), gr.update(visible=False)
    else:
        return gr.update(visible=False), gr.update(visible=True)
    
def ref_video_fn(path_of_ref_video):
    if path_of_ref_video is not None:
        return gr.update(value=True)
    else:
        return gr.update(value=False)

async def websocket_handler(websocket, path):
    """Handle WebSocket connections for real-time streaming"""
    streaming_app.streaming_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        streaming_app.streaming_clients.discard(websocket)

def start_websocket_server():
    """Start WebSocket server for real-time communication"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(websocket_handler, "localhost", 8765)
    loop.run_until_complete(start_server)
    loop.run_forever()

def sadtalker_streaming_demo(checkpoint_path='checkpoints', config_path='src/config', warpfn=None):
    global streaming_app
    streaming_app = StreamingSadTalker(checkpoint_path, config_path)

    # Start WebSocket server in background
    websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
    websocket_thread.start()

    with gr.Blocks(analytics_enabled=False, title="SadTalker Streaming") as sadtalker_interface:
        gr.Markdown("<div align='center'> <h2> 😭 SadTalker: Real-time Streaming with Nodding Avatar </span> </h2> \
                    <a style='font-size:18px;color: #efefef' href='https://arxiv.org/abs/2211.12194'>Arxiv</a> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; \
                    <a style='font-size:18px;color: #efefef' href='https://sadtalker.github.io'>Homepage</a>  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; \
                     <a style='font-size:18px;color: #efefef' href='https://github.com/Winfredy/SadTalker'> Github </div>")
        
        with gr.Row():
            with gr.Column(variant='panel'):
                with gr.Tabs(elem_id="sadtalker_source_image"):
                    with gr.TabItem('Upload image'):
                        with gr.Row():
                            source_image = gr.Image(label="Source image", source="upload", type="filepath", elem_id="img2img_image")

                with gr.Tabs(elem_id="sadtalker_driven_audio"):
                    with gr.TabItem('Upload OR TTS'):
                        with gr.Column(variant='panel'):
                            driven_audio = gr.Audio(label="Input audio", source="upload", type="filepath")

                        if sys.platform != 'win32' and not in_webui: 
                            try:
                                from src.utils.text2speech import TTSTalker
                                tts_talker = TTSTalker()
                                with gr.Column(variant='panel'):
                                    input_text = gr.Textbox(label="Generating audio from text", lines=5, placeholder="please enter some text here, we genreate the audio from text using @Coqui.ai TTS.")
                                    tts = gr.Button('Generate audio',elem_id="sadtalker_audio_generate", variant='primary')
                                    tts.click(fn=tts_talker.test, inputs=[input_text], outputs=[driven_audio])
                            except ImportError:
                                print("TTS not available. Text-to-speech feature disabled.")
                                pass
                            
            with gr.Column(variant='panel'): 
                with gr.Tabs(elem_id="sadtalker_checkbox"):
                    with gr.TabItem('Settings'):
                        gr.Markdown("need help? please visit our [best practice page](https://github.com/OpenTalker/SadTalker/blob/main/docs/best_practice.md) for more detials")
                        with gr.Column(variant='panel'):
                            pose_style = gr.Slider(minimum=0, maximum=46, step=1, label="Pose style", value=0)
                            size_of_image = gr.Radio([256, 512], value=256, label='face model resolution', info="use 256/512 model?")
                            preprocess_type = gr.Radio(['crop', 'resize','full', 'extcrop', 'extfull'], value='crop', label='preprocess', info="How to handle input image?")
                            is_still_mode = gr.Checkbox(label="Still Mode (fewer head motion, works with preprocess `full`)")
                            batch_size = gr.Slider(label="batch size in generation", step=1, maximum=10, value=2)
                            enhancer = gr.Checkbox(label="GFPGAN as Face enhancer")
                            submit = gr.Button('Generate', elem_id="sadtalker_generate", variant='primary')
                            
                with gr.Tabs(elem_id="sadtalker_genearted"):
                    with gr.TabItem('Live Preview'):
                        live_preview = gr.Image(label="Live Preview", height=300)
                        progress_bar = gr.Progress()
                        status_text = gr.Textbox(label="Status", value="Ready to generate", interactive=False)
                        
                        # WebSocket connection info
                        gr.Markdown("**For real-time streaming:** Open `streaming_client.html` in your browser")
                        
                    with gr.TabItem('Final Result'):
                        gen_video = gr.Video(label="Generated video", format="mp4")

        # Connect the streaming function
        submit.click(
            fn=streaming_app.generate_with_streaming, 
            inputs=[source_image, driven_audio, preprocess_type, is_still_mode,
                   enhancer, batch_size, size_of_image, pose_style], 
            outputs=[gen_video, live_preview, status_text]
        )

    return sadtalker_interface

if __name__ == "__main__":
    demo = sadtalker_streaming_demo()
    demo.queue()
    demo.launch()

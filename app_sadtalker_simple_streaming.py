#!/usr/bin/env python3
"""
Simplified SadTalker with Real-time Streaming Support
Uses a simpler approach that works better with Gradio
"""

import os
import sys
import gradio as gr
import numpy as np
import cv2
import time
import threading
from src.gradio_demo import SadTalker  

try:
    import webui  # in webui
    in_webui = True
except:
    in_webui = False

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

def sadtalker_simple_streaming_demo(checkpoint_path='checkpoints', config_path='src/config', warpfn=None):
    sad_talker = SadTalker(checkpoint_path, config_path, lazy_load=True)
    
    # Global variables for streaming
    current_frame = None
    streaming_state = {"active": False, "progress": 0, "status": "Ready"}
    
    def frame_callback(frame_data):
        """Callback function to handle streaming frames"""
        global current_frame, streaming_state
        
        try:
            if 'is_nodding' in frame_data and frame_data['is_nodding']:
                streaming_state["status"] = "Avatar is ready... nodding while processing"
            else:
                progress = frame_data['progress']
                frame_idx = frame_data['frame_idx']
                total_frames = frame_data['total_frames']
                streaming_state["progress"] = progress
                streaming_state["status"] = f"Generating frame {frame_idx + 1}/{total_frames} ({progress:.1%})"
            
            # Convert frame to displayable format
            frame = frame_data['frame']
            if len(frame.shape) == 4:
                frame = frame[0]  # Remove batch dimension
            
            # Convert tensor to numpy array
            if hasattr(frame, 'cpu'):
                frame = frame.cpu()
            if hasattr(frame, 'numpy'):
                frame = frame.numpy()
            
            # Convert to uint8 and transpose dimensions
            import numpy as np
            frame = np.transpose(frame, (1, 2, 0))
            frame = (frame * 255).astype(np.uint8)
            
            current_frame = frame
            print(f"Frame {frame_idx + 1}/{total_frames} generated and stored")
            
        except Exception as e:
            print(f"Error in frame_callback: {str(e)}")
            streaming_state["status"] = f"Error processing frame: {str(e)}"
        
        return current_frame
    
    def generate_with_streaming(source_image, driven_audio, preprocess_type, is_still_mode, 
                               enhancer, batch_size, size_of_image, pose_style):
        """Generate video with live streaming preview"""
        global streaming_state, current_frame
        
        try:
            streaming_state["active"] = True
            streaming_state["status"] = "Initializing..."
            
            # Start streaming generation
            result_path = sad_talker.test_streaming(
                source_image=source_image,
                driven_audio=driven_audio,
                preprocess=preprocess_type,
                still_mode=is_still_mode,
                use_enhancer=enhancer,
                batch_size=int(batch_size),
                size=int(size_of_image),
                pose_style=int(pose_style),
                callback=frame_callback
            )
            
            streaming_state["active"] = False
            streaming_state["status"] = "Generation complete!"
            
            return result_path, current_frame, streaming_state["status"]
            
        except Exception as e:
            streaming_state["active"] = False
            streaming_state["status"] = f"Error: {str(e)}"
            print(f"Error in generate_with_streaming: {e}")
            import traceback
            traceback.print_exc()
            return None, current_frame, streaming_state["status"]
    
    def update_preview():
        """Update the live preview periodically"""
        global current_frame, streaming_state
        
        if streaming_state["active"] and current_frame is not None:
            return current_frame, streaming_state["status"]
        elif current_frame is not None:
            return current_frame, streaming_state["status"]
        else:
            return None, "Ready to generate"

    with gr.Blocks(analytics_enabled=False, title="SadTalker Simple Streaming") as sadtalker_interface:
        gr.Markdown("<div align='center'> <h2> 😭 SadTalker: Simple Streaming with Live Preview </span> </h2> \
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
                        
                        # Auto-refresh button for live preview
                        refresh_btn = gr.Button('Refresh Preview', variant='secondary')
                        
                    with gr.TabItem('Final Result'):
                        gen_video = gr.Video(label="Generated video", format="mp4")

        # Connect the streaming function
        submit.click(
            fn=generate_with_streaming, 
            inputs=[source_image, driven_audio, preprocess_type, is_still_mode,
                   enhancer, batch_size, size_of_image, pose_style], 
            outputs=[gen_video, live_preview, status_text]
        )
        
        # Connect refresh button
        refresh_btn.click(
            fn=update_preview,
            inputs=[],
            outputs=[live_preview, status_text]
        )

    return sadtalker_interface

if __name__ == "__main__":
    demo = sadtalker_simple_streaming_demo()
    demo.queue()
    demo.launch()

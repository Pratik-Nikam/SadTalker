import os, sys
import gradio as gr
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

def sadtalker_demo(checkpoint_path='checkpoints', config_path='src/config', warpfn=None):

    sad_talker = SadTalker(checkpoint_path, config_path, lazy_load=True)
    
    # Global variables for streaming
    current_frame = None
    streaming_state = {"active": False, "progress": 0, "status": "Ready"}
    
    def frame_callback(frame_data):
        """Callback function to handle streaming frames"""
        nonlocal current_frame, streaming_state
        
        try:
            if 'is_nodding' in frame_data and frame_data['is_nodding']:
                streaming_state["status"] = "Avatar is ready... nodding while processing"
            else:
                progress = frame_data['progress']
                frame_idx = frame_data['frame_idx']
                total_frames = frame_data['total_frames']
                streaming_state["progress"] = progress
                streaming_state["current_frame"] = frame_idx + 1
                streaming_state["total_frames"] = total_frames
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
        nonlocal streaming_state, current_frame
        
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
            
            frame_info = f"Frame {streaming_state.get('current_frame', 0)}/{streaming_state.get('total_frames', 0)}"
            return result_path, current_frame, streaming_state["status"], frame_info
            
        except Exception as e:
            streaming_state["active"] = False
            streaming_state["status"] = f"Error: {str(e)}"
            return None, current_frame, streaming_state["status"], "Error occurred"
    
    def update_preview():
        """Update the live preview periodically"""
        nonlocal current_frame, streaming_state
        
        frame_info = f"Frame {streaming_state.get('current_frame', 0)}/{streaming_state.get('total_frames', 0)}"
        
        if streaming_state["active"] and current_frame is not None:
            return current_frame, streaming_state["status"], frame_info
        elif current_frame is not None:
            return current_frame, streaming_state["status"], frame_info
        else:
            return None, "Ready to generate", "Not started"

    with gr.Blocks(analytics_enabled=False) as sadtalker_interface:
        gr.Markdown("<div align='center'> <h2> Talking Avatar Generator </span> </h2> \
                    <a style='font-size:18px;color: #efefef' href='https://arxiv.org/abs/2211.12194'>Arxiv</a> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; \
                    <a style='font-size:18px;color: #efefef' href='https://sadtalker.github.io'>Homepage</a>  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; \
                     <a style='font-size:18px;color: #efefef' href='https://github.com/Winfredy/SadTalker'> Github </div>")
        
        with gr.Row().style(equal_height=False):
            with gr.Column(variant='panel'):
                with gr.Tabs(elem_id="sadtalker_source_image"):
                    with gr.TabItem('Upload image'):
                        with gr.Row():
                            source_image = gr.Image(label="Source image", source="upload", type="filepath", elem_id="img2img_image").style(width=512)

                with gr.Tabs(elem_id="sadtalker_driven_audio"):
                    with gr.TabItem('Upload OR TTS'):
                        with gr.Column(variant='panel'):
                            driven_audio = gr.Audio(label="Input audio", source="upload", type="filepath")

                        # if sys.platform != 'win32' and not in_webui: 
                        #     from src.utils.text2speech import TTSTalker
                        #     tts_talker = TTSTalker()
                        #     with gr.Column(variant='panel'):
                        #         input_text = gr.Textbox(label="Generating audio from text", lines=5, placeholder="please enter some text here, we genreate the audio from text using @Coqui.ai TTS.")
                        #         tts = gr.Button('Generate audio',elem_id="sadtalker_audio_generate", variant='primary')
                        #         tts.click(fn=tts_talker.test, inputs=[input_text], outputs=[driven_audio])

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
                            # width = gr.Slider(minimum=64, elem_id="img2img_width", maximum=2048, step=8, label="Manually Crop Width", value=512) # img2img_width
                            # height = gr.Slider(minimum=64, elem_id="img2img_height", maximum=2048, step=8, label="Manually Crop Height", value=512) # img2img_width
                            pose_style = gr.Slider(minimum=0, maximum=46, step=1, label="Pose style", value=0) # 
                            size_of_image = gr.Radio([256, 512], value=256, label='face model resolution', info="use 256/512 model?") # 
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
                        
                        # Add refresh button and auto-refresh toggle
                        with gr.Row():
                            refresh_btn = gr.Button('🔄 Refresh Preview', elem_id="refresh_preview", variant='secondary', size='sm')
                            auto_refresh = gr.Checkbox(label="Auto-refresh during generation", value=True)
                        
                        # Add frame counter
                        frame_counter = gr.Textbox(label="Frame Progress", value="Not started", interactive=False)
                        
                    with gr.TabItem('Final Result'):
                        gen_video = gr.Video(label="Generated video", format="mp4")

        if warpfn:
            submit.click(
                        fn=warpfn(sad_talker.test), 
                        inputs=[source_image,
                                driven_audio,
                                preprocess_type,
                                is_still_mode,
                                enhancer,
                                batch_size,                            
                                size_of_image,
                                pose_style
                                ], 
                        outputs=[gen_video]
                        )
        else:
            submit.click(
                        fn=generate_with_streaming, 
                        inputs=[source_image,
                                driven_audio,
                                preprocess_type,
                                is_still_mode,
                                enhancer,
                                batch_size,                            
                                size_of_image,
                                pose_style
                                ], 
                        outputs=[gen_video, live_preview, status_text, frame_counter]
                        )
            
            # Connect refresh button
            refresh_btn.click(
                fn=update_preview,
                inputs=[],
                outputs=[live_preview, status_text, frame_counter]
            )
        
        # Add JavaScript for real-time updates
        js_code = """
        <script>
        function startPreviewUpdates() {
            let isGenerating = false;
            let autoRefresh = true;
            let pollingInterval = null;
            
            function updatePreview() {
                if (isGenerating && autoRefresh) {
                    // Trigger a refresh of the live preview
                    const refreshBtn = document.querySelector('button[data-testid="refresh_preview"]');
                    if (refreshBtn) {
                        refreshBtn.click();
                    }
                    
                    // Check if generation is complete
                    const statusEl = document.querySelector('input[data-testid="status_text"]');
                    if (statusEl) {
                        const statusText = statusEl.value;
                        if (statusText.includes('Generation complete') || statusText.includes('Error:')) {
                            isGenerating = false;
                            if (pollingInterval) {
                                clearInterval(pollingInterval);
                                pollingInterval = null;
                            }
                        }
                    }
                }
            }
            
            function startPolling() {
                if (pollingInterval) {
                    clearInterval(pollingInterval);
                }
                pollingInterval = setInterval(updatePreview, 2000); // Poll every 2 seconds
            }
            
            // Listen for generation start
            document.addEventListener('click', function(e) {
                if (e.target && e.target.textContent && e.target.textContent.includes('Generate')) {
                    isGenerating = true;
                    setTimeout(startPolling, 3000); // Start polling after 3 seconds
                }
            });
            
            // Listen for auto-refresh toggle
            document.addEventListener('change', function(e) {
                if (e.target && e.target.type === 'checkbox' && e.target.labels[0].textContent.includes('Auto-refresh')) {
                    autoRefresh = e.target.checked;
                }
            });
            
            // Add visual feedback
            function addGenerationIndicator() {
                const generateBtn = document.querySelector('button[data-testid="sadtalker_generate"]');
                if (generateBtn && isGenerating) {
                    generateBtn.style.background = 'linear-gradient(45deg, #ff6b6b, #ffa500)';
                    generateBtn.textContent = '🔄 Generating...';
                } else if (generateBtn) {
                    generateBtn.style.background = '';
                    generateBtn.textContent = 'Generate';
                }
            }
            
            setInterval(addGenerationIndicator, 1000);
        }
        
        // Start when page loads
        document.addEventListener('DOMContentLoaded', startPreviewUpdates);
        </script>
        """
        
        sadtalker_interface.add(gr.HTML(js_code))

    return sadtalker_interface
 

if __name__ == "__main__":

    demo = sadtalker_demo()
    demo.queue()
    demo.launch()



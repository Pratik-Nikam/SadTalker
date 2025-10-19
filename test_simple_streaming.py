#!/usr/bin/env python3
"""
Simple test for SadTalker streaming functionality
"""

def test_streaming_structure():
    """Test if the streaming files exist and have the right structure"""
    print("🧪 Testing SadTalker Streaming Structure")
    print("=" * 50)
    
    import os
    
    # Check if streaming files exist
    files_to_check = [
        'app_sadtalker.py',
        'app_sadtalker_simple_streaming.py', 
        'src/facerender/animate.py',
        'src/gradio_demo.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
            
            # Check for streaming functions
            with open(file_path, 'r') as f:
                content = f.read()
                
            if 'test_streaming' in content:
                print(f"✅ {file_path} contains streaming function")
            if 'generate_streaming' in content:
                print(f"✅ {file_path} contains streaming generation")
            if 'frame_callback' in content:
                print(f"✅ {file_path} contains frame callback")
                
        else:
            print(f"❌ {file_path} not found")
            return False
    
    print("\n🎉 All streaming files are present!")
    print("\n📋 How to test:")
    print("1. Run: python app_sadtalker.py")
    print("2. Upload an image and audio")
    print("3. Click Generate")
    print("4. Watch the console for frame generation messages")
    print("5. Check the Live Preview tab for updates")
    
    return True

if __name__ == "__main__":
    test_streaming_structure()

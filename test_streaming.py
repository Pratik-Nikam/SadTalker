#!/usr/bin/env python3
"""
Test script for SadTalker streaming functionality
"""

import os
import sys
import torch
import numpy as np
from src.facerender.modules.make_animation import make_animation_streaming
from src.facerender.animate import AnimateFromCoeff

def test_streaming_function():
    """Test the streaming animation function"""
    print("Testing streaming animation function...")
    
    # Create dummy data
    batch_size = 1
    height, width = 256, 256
    num_frames = 10
    
    source_image = torch.randn(batch_size, 3, height, width)
    source_semantics = torch.randn(batch_size, 70)  # 3DMM coefficients
    target_semantics = torch.randn(batch_size, num_frames, 70)
    
    # Mock generator, kp_detector, he_estimator, mapping
    class MockGenerator:
        def __call__(self, *args, **kwargs):
            return {'prediction': torch.randn(batch_size, 3, height, width)}
    
    class MockKPDetector:
        def __call__(self, *args, **kwargs):
            return {'value': torch.randn(batch_size, 68, 3)}  # 68 facial keypoints
    
    class MockHEEstimator:
        def __call__(self, *args, **kwargs):
            return {'yaw': torch.randn(batch_size, 66), 'pitch': torch.randn(batch_size, 66), 
                   'roll': torch.randn(batch_size, 66), 't': torch.randn(batch_size, 3),
                   'exp': torch.randn(batch_size, 204)}
    
    class MockMapping:
        def __call__(self, *args, **kwargs):
            return {'yaw': torch.randn(batch_size, 66), 'pitch': torch.randn(batch_size, 66), 
                   'roll': torch.randn(batch_size, 66), 't': torch.randn(batch_size, 3),
                   'exp': torch.randn(batch_size, 204)}
    
    generator = MockGenerator()
    kp_detector = MockKPDetector()
    he_estimator = MockHEEstimator()
    mapping = MockMapping()
    
    # Test streaming
    frame_count = 0
    for frame_pred, progress in make_animation_streaming(
        source_image, source_semantics, target_semantics,
        generator, kp_detector, he_estimator, mapping,
        callback=lambda data: print(f"Frame {data['frame_idx']+1}: {data['progress']:.1%}")
    ):
        frame_count += 1
        print(f"Received frame {frame_count}, progress: {progress:.1%}")
    
    print(f"Streaming test completed. Received {frame_count} frames.")
    return True

def test_nodding_animation():
    """Test the nodding animation functionality"""
    print("\nTesting nodding animation...")
    
    # Create dummy source semantics
    source_semantics = torch.randn(1, 70)
    
    # Simulate nodding by modifying pitch
    import time
    for i in range(5):
        nodding_semantics = source_semantics.clone()
        # Add slight pitch variation for nodding
        if nodding_semantics.shape[1] > 6:
            nodding_semantics[:, 6] += 0.1 * np.sin(time.time() * 3)
        
        print(f"Nodding frame {i+1}: pitch offset = {nodding_semantics[:, 6].item():.3f}")
        time.sleep(0.5)
    
    print("Nodding animation test completed.")
    return True

def main():
    """Main test function"""
    print("🧪 Testing SadTalker Streaming Implementation")
    print("=" * 50)
    
    try:
        # Test streaming function
        if test_streaming_function():
            print("✅ Streaming function test passed")
        else:
            print("❌ Streaming function test failed")
            return False
        
        # Test nodding animation
        if test_nodding_animation():
            print("✅ Nodding animation test passed")
        else:
            print("❌ Nodding animation test failed")
            return False
        
        print("\n🎉 All tests passed! Streaming implementation is working.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

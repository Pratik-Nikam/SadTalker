"""
Fast Preview Mode for SadTalker Streaming
Generates low-resolution frames quickly for real-time preview
"""

import os
import cv2
import yaml
import numpy as np
import warnings
from skimage import img_as_ubyte
import safetensors
import safetensors.torch 
import torch
import torch.nn.functional as F
warnings.filterwarnings('ignore')

from src.facerender.modules.keypoint_detector import HEEstimator, KPDetector
from src.facerender.modules.mapping import MappingNet
from src.facerender.modules.generator import OcclusionAwareGenerator, OcclusionAwareSPADEGenerator
from src.facerender.modules.make_animation import keypoint_transformation

class FastPreviewGenerator:
    """
    Fast preview generator that creates low-resolution frames quickly
    for real-time streaming while high-quality frames generate in background
    """
    
    def __init__(self, sadtalker_path, device, preview_size=128):
        self.device = device
        self.preview_size = preview_size
        
        # Load a lightweight version of the models
        with open(sadtalker_path['facerender_yaml']) as f:
            config = yaml.safe_load(f)
        
        # Use smaller models for preview
        generator = OcclusionAwareSPADEGenerator(**config['model_params']['generator_params'],
                                                **config['model_params']['common_params'])
        kp_extractor = KPDetector(**config['model_params']['kp_detector_params'],
                                **config['model_params']['common_params'])
        he_estimator = HEEstimator(**config['model_params']['he_estimator_params'],
                               **config['model_params']['common_params'])
        mapping = MappingNet(**config['model_params']['mapping_params'])

        generator.to(device)
        kp_extractor.to(device)
        he_estimator.to(device)
        mapping.to(device)
        
        # Load weights
        if sadtalker_path is not None:
            if 'checkpoint' in sadtalker_path:
                self.load_cpk_facevid2vid_safetensor(sadtalker_path['checkpoint'], 
                                                   kp_detector=kp_extractor, 
                                                   generator=generator, 
                                                   he_estimator=None)
            else:
                self.load_cpk_facevid2vid(sadtalker_path['free_view_checkpoint'], 
                                        kp_detector=kp_extractor, 
                                        generator=generator, 
                                        he_estimator=he_estimator)

        if sadtalker_path['mappingnet_checkpoint'] is not None:
            self.load_cpk_mapping(sadtalker_path['mappingnet_checkpoint'], mapping=mapping)

        self.kp_extractor = kp_extractor
        self.generator = generator
        self.he_estimator = he_estimator
        self.mapping = mapping

        self.kp_extractor.eval()
        self.generator.eval()
        self.he_estimator.eval()
        self.mapping.eval()
        
        self.device = device
    
    def load_cpk_facevid2vid_safetensor(self, checkpoint_path, generator=None, 
                        kp_detector=None, he_estimator=None,  
                        device="cpu"):
        checkpoint = safetensors.torch.load_file(checkpoint_path)

        if generator is not None:
            x_generator = {}
            for k,v in checkpoint.items():
                if 'generator' in k:
                    x_generator[k.replace('generator.', '')] = v
            generator.load_state_dict(x_generator)
        if kp_detector is not None:
            x_generator = {}
            for k,v in checkpoint.items():
                if 'kp_extractor' in k:
                    x_generator[k.replace('kp_extractor.', '')] = v
            kp_detector.load_state_dict(x_generator)
        if he_estimator is not None:
            x_generator = {}
            for k,v in checkpoint.items():
                if 'he_estimator' in k:
                    x_generator[k.replace('he_estimator.', '')] = v
            he_estimator.load_state_dict(x_generator)
        
        return None

    def load_cpk_facevid2vid(self, checkpoint_path, generator=None, discriminator=None, 
                        kp_detector=None, he_estimator=None, optimizer_generator=None, 
                        optimizer_discriminator=None, optimizer_kp_detector=None, 
                        optimizer_he_estimator=None, device="cpu"):
        checkpoint = torch.load(checkpoint_path, map_location=torch.device(device))
        if generator is not None:
            generator.load_state_dict(checkpoint['generator'])
        if kp_detector is not None:
            kp_detector.load_state_dict(checkpoint['kp_detector'])
        if he_estimator is not None:
            he_estimator.load_state_dict(checkpoint['he_estimator'])
        return checkpoint['epoch']
    
    def load_cpk_mapping(self, checkpoint_path, mapping=None, discriminator=None,
                 optimizer_mapping=None, optimizer_discriminator=None, device='cpu'):
        checkpoint = torch.load(checkpoint_path,  map_location=torch.device(device))
        if mapping is not None:
            mapping.load_state_dict(checkpoint['mapping'])
        return checkpoint['epoch']

    def generate_fast_preview(self, x, callback=None):
        """
        Generate fast preview frames for real-time streaming
        """
        source_image = x['source_image'].type(torch.FloatTensor)
        source_semantics = x['source_semantics'].type(torch.FloatTensor)
        target_semantics = x['target_semantics_list'].type(torch.FloatTensor) 
        
        # Resize source image for faster processing
        source_image = F.interpolate(source_image, size=(self.preview_size, self.preview_size), 
                                   mode='bilinear', align_corners=False)
        
        source_image = source_image.to(self.device)
        source_semantics = source_semantics.to(self.device)
        target_semantics = target_semantics.to(self.device)
        
        if 'yaw_c_seq' in x:
            yaw_c_seq = x['yaw_c_seq'].type(torch.FloatTensor).to(self.device)
        else:
            yaw_c_seq = None
        if 'pitch_c_seq' in x:
            pitch_c_seq = x['pitch_c_seq'].type(torch.FloatTensor).to(self.device)
        else:
            pitch_c_seq = None
        if 'roll_c_seq' in x:
            roll_c_seq = x['roll_c_seq'].type(torch.FloatTensor).to(self.device)
        else:
            roll_c_seq = None

        frame_num = x['frame_num']
        
        with torch.no_grad():
            kp_canonical = self.kp_extractor(source_image)
            he_source = self.mapping(source_semantics)
            kp_source = keypoint_transformation(kp_canonical, he_source)
        
            total_frames = target_semantics.shape[1]
            
            for frame_idx in range(total_frames):
                target_semantics_frame = target_semantics[:, frame_idx]
                he_driving = self.mapping(target_semantics_frame)
                
                if yaw_c_seq is not None:
                    he_driving['yaw_in'] = yaw_c_seq[:, frame_idx]
                if pitch_c_seq is not None:
                    he_driving['pitch_in'] = pitch_c_seq[:, frame_idx] 
                if roll_c_seq is not None:
                    he_driving['roll_in'] = roll_c_seq[:, frame_idx] 
                
                kp_driving = keypoint_transformation(kp_canonical, he_driving)
                kp_norm = kp_driving
                
                # Generate frame with reduced precision for speed
                with torch.cuda.amp.autocast(enabled=self.device == 'cuda'):
                    out = self.generator(source_image, kp_source=kp_source, kp_driving=kp_norm)
                
                progress = (frame_idx + 1) / total_frames
                
                # Call callback if provided
                if callback:
                    frame_data = {
                        'frame': out['prediction'],
                        'frame_idx': frame_idx,
                        'progress': progress,
                        'total_frames': total_frames,
                        'is_preview': True,
                        'resolution': self.preview_size
                    }
                    callback(frame_data)
                
                yield out['prediction'], progress

    def create_nodding_animation(self, source_image, source_semantics, callback=None):
        """
        Create a simple nodding animation for idle state
        """
        import time
        
        # Resize for preview
        source_image = F.interpolate(source_image, size=(self.preview_size, self.preview_size), 
                                   mode='bilinear', align_corners=False)
        
        source_image = source_image.to(self.device)
        source_semantics = source_semantics.to(self.device)
        
        with torch.no_grad():
            kp_canonical = self.kp_extractor(source_image)
            he_source = self.mapping(source_semantics)
            kp_source = keypoint_transformation(kp_canonical, he_source)
            
            # Create nodding effect
            nodding_semantics = source_semantics.clone()
            if nodding_semantics.shape[1] > 6:
                nodding_semantics[:, 6] += 0.03 * np.sin(time.time() * 2)  # Gentle nod
            
            he_driving = self.mapping(nodding_semantics)
            kp_driving = keypoint_transformation(kp_canonical, he_driving)
            
            with torch.cuda.amp.autocast(enabled=self.device == 'cuda'):
                nodding_out = self.generator(source_image, kp_source=kp_source, kp_driving=kp_driving)
            
            if callback:
                frame_data = {
                    'frame': nodding_out['prediction'],
                    'frame_idx': -1,
                    'progress': 0.0,
                    'total_frames': 1,
                    'is_nodding': True,
                    'is_preview': True,
                    'resolution': self.preview_size
                }
                callback(frame_data)
            
            return nodding_out['prediction']

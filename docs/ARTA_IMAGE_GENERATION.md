# Arta Image Generation API Documentation

## Overview

Arta is an advanced image generation service that provides high-quality artistic image generation with support for multiple styles and aspect ratios. This documentation covers how Arta is integrated into the JakeySelfBot project.

## Key Features

### 1. Artistic Styles
Arta supports 49 different artistic styles for image generation:
- Medieval
- Vincent Van Gogh
- Fantasy Art
- Watercolor
- Photographic
- SDXL 1.0 (default)
- And 44 more styles

### 2. Aspect Ratios
Arta supports 9 different aspect ratios:
- 1:1 (Square)
- 2:3 (Portrait)
- 3:2 (Landscape)
- 3:4 (Tall Portrait)
- 4:3 (Wide Landscape)
- 9:16 (Mobile Portrait)
- 16:9 (Mobile Landscape)
- 9:21 (Ultra Portrait)
- 21:9 (Ultra Landscape)

## Authentication

Arta uses Firebase authentication to generate tokens:
- Makes requests to Google Identity Toolkit
- Uses specific Android headers and certificates
- Generates temporary auth tokens for API access

## Image Generation Process

### 1. Request Submission
- Sends multipart form data with prompt, style, ratio, steps, etc.
- Returns a record_id for status checking

### 2. Status Polling
- Polls endpoint with record_id to check generation status
- Status values: QUEUED, PROCESSING, DONE, FAILED
- Returns image URLs when generation is complete

## Integration in JakeySelfBot

### Tool Manager Integration
The `generate_image` tool in `tools/tool_manager.py` has been updated to use Arta:
- Parameters: prompt, model (style), width, height
- Width/height are converted to aspect ratios automatically
- Default style is "SDXL 1.0"

### Image Generator
The `media/image_generator.py` module now uses Arta:
- Converts Pollinations-style parameters to Arta parameters
- Maintains backward compatibility
- Handles authentication and status polling

## Usage Examples

### Basic Usage
```
%image Fantasy Art a degenerate gambler at a casino
```

### Style-Specific Generation
```
%image Vincent Van Gogh a poker table with chips
```

### Aspect Ratio Usage
```
%image 16:9 cinematic a slot machine winning big
```

## Technical Implementation

### Authentication Flow
1. Generate Firebase auth token
2. Use token for all subsequent requests
3. Handle token expiration and renewal

### Error Handling
- Detailed error messages from API
- Timeout handling for long generation processes
- Retry logic for temporary failures

### Asynchronous Processing
- Non-blocking image generation
- Status polling with configurable intervals
- Maximum wait time of 5 minutes

## Advantages Over Previous Implementation

### 1. Better Quality
- Professional artistic styles
- Higher resolution outputs
- Better detail and composition

### 2. More Control
- 49 artistic styles to choose from
- 9 aspect ratios for flexibility
- Fine-grained control over generation parameters

### 3. Better Reliability
- Proper authentication system
- Detailed status reporting
- Comprehensive error handling

## Backward Compatibility

The implementation maintains full backward compatibility:
- Same function signatures as Pollinations
- Automatic parameter conversion
- Same response format (image URLs)

## Configuration

No additional configuration is required. The Arta API uses hardcoded endpoints and authentication parameters based on the original arta.go implementation.
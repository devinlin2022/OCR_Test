document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const captureBtn = document.getElementById('capture-btn');
    const switchCameraBtn = document.getElementById('switch-camera-btn');
    const captureOverlay = document.getElementById('capture-overlay');
    
    // Result elements
    const capturedImage = document.getElementById('captured-image');
    const imagePlaceholder = document.getElementById('image-placeholder');
    const loadingState = document.getElementById('loading-state');
    const resultContent = document.getElementById('result-content');
    
    let currentStream = null;
    let useFrontCamera = false; // default to back camera for OCR

    // Initialize Camera
    async function initCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }

        const constraints = {
            video: {
                facingMode: useFrontCamera ? 'user' : 'environment',
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        };

        try {
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = currentStream;
            document.getElementById('connection-status').textContent = 'Camera Active';
            document.getElementById('connection-status').style.color = 'var(--success)';
        } catch (err) {
            console.error('Error accessing camera:', err);
            document.getElementById('connection-status').textContent = 'Camera Error';
            document.getElementById('connection-status').style.color = 'var(--error)';
            alert('Could not access camera. Please ensure permissions are granted.');
        }
    }

    // Switch Camera
    switchCameraBtn.addEventListener('click', () => {
        useFrontCamera = !useFrontCamera;
        initCamera();
    });

    // Capture Image and Send
    captureBtn.addEventListener('click', async () => {
        if (!currentStream) return;

        // Visual flash effect
        captureOverlay.style.opacity = '1';
        setTimeout(() => captureOverlay.style.opacity = '0', 100);

        // Set canvas size to video size
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw video frame to canvas
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to blob
        canvas.toBlob(async (blob) => {
            if (!blob) return;

            // Show loading
            resultContent.classList.add('hidden');
            loadingState.classList.remove('hidden');
            captureBtn.disabled = true;

            // Show captured image preview
            const imageUrl = URL.createObjectURL(blob);
            capturedImage.src = imageUrl;
            capturedImage.style.display = 'block';
            imagePlaceholder.style.display = 'none';

            // Gather form data
            const formData = new FormData(document.getElementById('config-form'));
            formData.append('image', blob, 'capture.jpg');

            try {
                // Determine API URL (relative works on Vercel)
                const apiUrl = '/api/ocr';
                
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}`);
                }

                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error);
                }

                // Update UI with results
                document.getElementById('res-correct').textContent = result.correct_answer || '-';
                document.getElementById('res-ocr').textContent = result.ocr_result || 'No text detected';
                
                // Color formatting for OCR result based on match
                const resOcrElem = document.getElementById('res-ocr');
                if (result.ocr_result === result.correct_answer && result.ocr_result) {
                    resOcrElem.style.color = 'var(--success)';
                } else {
                    resOcrElem.style.color = 'var(--error)';
                }

                document.getElementById('res-similarity').textContent = result.similarity_rate || '-';
                
                const syncElem = document.getElementById('res-sync');
                syncElem.textContent = result.sheets_saved ? 'Success' : 'Failed/Skipped';
                syncElem.style.color = result.sheets_saved ? 'var(--success)' : 'var(--text-muted)';

                // AI Levels
                document.getElementById('eval-4').textContent = result.ai_levels && result.ai_levels['4'] ? result.ai_levels['4'] : '-';
                document.getElementById('eval-3').textContent = result.ai_levels && result.ai_levels['3'] ? result.ai_levels['3'] : '-';
                document.getElementById('eval-2').textContent = result.ai_levels && result.ai_levels['2'] ? result.ai_levels['2'] : '-';
                document.getElementById('eval-1').textContent = result.ai_levels && result.ai_levels['1'] ? result.ai_levels['1'] : '-';

            } catch (error) {
                console.error('Error during analysis:', error);
                alert('Analysis failed: ' + error.message);
            } finally {
                // Hide loading
                loadingState.classList.add('hidden');
                resultContent.classList.remove('hidden');
                captureBtn.disabled = false;
            }

        }, 'image/jpeg', 0.9);
    });

    // Start camera on load
    initCamera();
});

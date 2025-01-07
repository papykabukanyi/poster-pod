// Initialize Plyr for all audio players
document.addEventListener('DOMContentLoaded', () => {
    // Initialize all audio players
    const players = Plyr.setup('.plyr', {
        controls: [
            'play',
            'progress',
            'current-time',
            'duration',
            'mute',
            'volume',
        ]
    });

    // Handle player events
    players.forEach(player => {
        // Update localStorage with current time for resume functionality
        player.on('timeupdate', (event) => {
            const audio = event.target;
            const source = audio.querySelector('source').src;
            localStorage.setItem(`podcast-${source}`, player.currentTime);
        });

        // Resume from last position
        player.on('ready', (event) => {
            const audio = event.target;
            const source = audio.querySelector('source').src;
            const lastPosition = localStorage.getItem(`podcast-${source}`);
            if (lastPosition) {
                player.currentTime = parseFloat(lastPosition);
            }
        });
    });
});

// Handle file upload with drag and drop
document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const uploadZone = document.querySelector('.upload-zone');
    
    if (uploadForm && uploadZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            uploadZone.classList.add('dragover');
        }

        function unhighlight() {
            uploadZone.classList.remove('dragover');
        }

        uploadZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }

        function handleFiles(files) {
            if (files.length > 0) {
                const fileInput = uploadForm.querySelector('input[type="file"]');
                fileInput.files = files;
            }
        }
    }
});

// Handle form submission with progress
document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            
            try {
                submitButton.classList.add('loading');
                submitButton.disabled = true;
                submitButton.textContent = 'Uploading...';
                
                const formData = new FormData(uploadForm);
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    window.location.reload();
                } else {
                    throw new Error('Upload failed');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Upload failed. Please try again.');
            } finally {
                submitButton.classList.remove('loading');
                submitButton.disabled = false;
                submitButton.textContent = originalText;
            }
        });
    }
});

// Add keyboard shortcuts for player controls
document.addEventListener('keydown', (e) => {
    const activePlayer = Plyr.setup('.plyr--playing')[0];
    
    if (activePlayer) {
        switch(e.key) {
            case ' ':
                if (!e.target.matches('input, textarea')) {
                    e.preventDefault();
                    activePlayer.togglePlay();
                }
                break;
            case 'ArrowLeft':
                if (!e.target.matches('input, textarea')) {
                    e.preventDefault();
                    activePlayer.rewind(10);
                }
                break;
            case 'ArrowRight':
                if (!e.target.matches('input, textarea')) {
                    e.preventDefault();
                    activePlayer.forward(10);
                }
                break;
            case 'm':
                if (!e.target.matches('input, textarea')) {
                    e.preventDefault();
                    activePlayer.toggleMute();
                }
                break;
        }
    }
});
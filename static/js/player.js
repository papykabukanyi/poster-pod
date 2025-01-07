document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const preloader = document.getElementById('preloader');
        preloader.style.opacity = '0';
        preloader.style.transition = 'opacity 0.3s ease';
        setTimeout(() => {
            preloader.style.display = 'none';
        }, 300);
    }, 1500); // Reduced from 3000 to 1500ms for faster animation
});

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

// Handle like functionality
async function likePodcast(podcastId) {
    try {
        const response = await fetch(`/like/${podcastId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            const likeBtn = document.querySelector(`[onclick="likePodcast(${podcastId})"]`);
            const likesCount = likeBtn.querySelector('.likes-count');
            likesCount.textContent = data.likes;
            
            // Add visual feedback
            likeBtn.classList.add('text-red-500');
            setTimeout(() => {
                likeBtn.classList.remove('text-red-500');
            }, 200);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

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

// Add progress tracking for audio playback
document.addEventListener('DOMContentLoaded', () => {
    const players = document.querySelectorAll('.plyr');
    
    players.forEach(player => {
        const progressBar = document.createElement('div');
        progressBar.className = 'progress-bar mt-2';
        const progressFill = document.createElement('div');
        progressFill.className = 'progress-bar-fill';
        progressBar.appendChild(progressFill);
        player.parentElement.appendChild(progressBar);

        player.addEventListener('timeupdate', () => {
            const progress = (player.currentTime / player.duration) * 100;
            progressFill.style.width = `${progress}%`;
        });
    });
});
// Add preloader functionality
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const preloader = document.getElementById('preloader');
        preloader.style.opacity = '0';
        preloader.style.transition = 'opacity 0.5s ease';
        setTimeout(() => {
            preloader.style.display = 'none';
        }, 500);
    }, 3000);
});

// Share functionality
function sharePodcast(podcastId) {
    const shareUrl = `${window.location.origin}/podcast/${podcastId}`;
    
    navigator.clipboard.writeText(shareUrl).then(() => {
        const notification = document.getElementById('shareNotification');
        notification.classList.add('share-notification-show');
        
        setTimeout(() => {
            notification.classList.remove('share-notification-show');
        }, 3000);
    });
}

// Like limitation using localStorage
function likePodcast(podcastId) {
    const likeKey = `podcast-like-${podcastId}`;
    if (localStorage.getItem(likeKey)) {
        return;
    }

    fetch(`/like/${podcastId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        const likeBtn = document.querySelector(`[data-podcast-id="${podcastId}"]`);
        const likesCount = likeBtn.querySelector('.likes-count');
        likesCount.textContent = data.likes;
        localStorage.setItem(likeKey, 'true');
        
        likeBtn.classList.add('text-red-500');
        setTimeout(() => {
            likeBtn.classList.remove('text-red-500');
        }, 200);
    })
    .catch(error => console.error('Error:', error));
}
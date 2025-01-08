document.addEventListener('DOMContentLoaded', () => {
    // Preloader handling
    const preloader = document.getElementById('preloader');
    if (preloader) {
        setTimeout(() => {
            preloader.style.opacity = '0';
            setTimeout(() => {
                preloader.style.display = 'none';
            }, 300);
        }, 1500);
    }

    // Initialize players
    const players = document.querySelectorAll('.audio-player');
    let activeWavesurfer = null; // Track currently playing wavesurfer
    const wavesurfers = [];

    players.forEach((player, index) => {
        const audio = player.querySelector('audio');
        const container = player.querySelector('.waveform-container');
        const playButton = player.querySelector('.play-button');
        const volumeSlider = player.querySelector('.volume-slider');

        if (!audio || !container) return;

        // Create canvas for gradient
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Define the waveform gradient
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height * 1.35);
        gradient.addColorStop(0, '#656666'); // Top color
        gradient.addColorStop((canvas.height * 0.7) / canvas.height, '#656666'); // Top color
        gradient.addColorStop((canvas.height * 0.7 + 1) / canvas.height, '#ffffff'); // White line
        gradient.addColorStop((canvas.height * 0.7 + 2) / canvas.height, '#ffffff'); // White line
        gradient.addColorStop((canvas.height * 0.7 + 3) / canvas.height, '#B1B1B1'); // Bottom color
        gradient.addColorStop(1, '#B1B1B1'); // Bottom color

        // Define the progress gradient
        const progressGradient = ctx.createLinearGradient(0, 0, 0, canvas.height * 1.35);
        progressGradient.addColorStop(0, '#EE772F'); // Top color
        progressGradient.addColorStop((canvas.height * 0.7) / canvas.height, '#EB4926'); // Top color
        progressGradient.addColorStop((canvas.height * 0.7 + 1) / canvas.height, '#ffffff'); // White line
        progressGradient.addColorStop((canvas.height * 0.7 + 2) / canvas.height, '#ffffff'); // White line
        progressGradient.addColorStop((canvas.height * 0.7 + 3) / canvas.height, '#F6B094'); // Bottom color
        progressGradient.addColorStop(1, '#F6B094'); // Bottom color

        // Create the waveform
        const wavesurfer = WaveSurfer.create({
            container: container,
            waveColor: '#656666', // Light gray
            progressColor: '#333333', // Dark gray for progress
            barWidth: 2,
            barHeight: 0.6, // Shorter bars
            barGap: 2,
            height: 40,
            normalize: true,
            url: audio.src,
        });

        wavesurfers.push(wavesurfer);

        // Play/pause handling with single player logic
        playButton.addEventListener('click', () => {
            if (activeWavesurfer && activeWavesurfer !== wavesurfer) {
                // Stop currently playing audio
                activeWavesurfer.pause();
                // Reset play/pause button of previously playing audio
                const activePlayers = document.querySelectorAll('.audio-player');
                activePlayers.forEach(p => {
                    const btn = p.querySelector('.play-button');
                    btn.querySelector('.play-icon').classList.remove('hidden');
                    btn.querySelector('.pause-icon').classList.add('hidden');
                });
            }

            wavesurfer.playPause();
            playButton.querySelector('.play-icon').classList.toggle('hidden');
            playButton.querySelector('.pause-icon').classList.toggle('hidden');
            
            if (wavesurfer.isPlaying()) {
                activeWavesurfer = wavesurfer;
            } else {
                activeWavesurfer = null;
            }
        });

        // Handle play/pause events
        wavesurfer.on('play', () => {
            activeWavesurfer = wavesurfer;
        });

        wavesurfer.on('pause', () => {
            if (activeWavesurfer === wavesurfer) {
                activeWavesurfer = null;
            }
        });

        // Handle finish event
        wavesurfer.on('finish', () => {
            playButton.querySelector('.play-icon').classList.remove('hidden');
            playButton.querySelector('.pause-icon').classList.add('hidden');
            activeWavesurfer = null;
        });

        // Volume control
        volumeSlider.addEventListener('input', (e) => {
            wavesurfer.setVolume(e.target.value);
        });

        // Current time & duration
        const formatTime = (seconds) => {
            const minutes = Math.floor(seconds / 60);
            const secondsRemainder = Math.round(seconds) % 60;
            const paddedSeconds = `0${secondsRemainder}`.slice(-2);
            return `${minutes}:${paddedSeconds}`;
        };

        const timeEl = player.querySelector('#time');
        const durationEl = player.querySelector('#duration');
        wavesurfer.on('ready', () => {
            durationEl.textContent = formatTime(wavesurfer.getDuration());
        });
        wavesurfer.on('audioprocess', () => {
            timeEl.textContent = formatTime(wavesurfer.getCurrentTime());
        });

        // Hover effect
        const hover = player.querySelector('#hover');
        container.addEventListener('pointermove', (e) => {
            hover.style.width = `${e.offsetX}px`;
        });
    });

    // Update view count
    function updateViewCount(podcastId) {
        const viewKey = `podcast-view-${podcastId}`;
        if (!localStorage.getItem(viewKey)) {
            fetch(`/views/${podcastId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                const viewCount = document.querySelector(`[data-view-count="${podcastId}"]`);
                if (viewCount) {
                    viewCount.textContent = `${data.views} listens`;
                }
                localStorage.setItem(viewKey, 'true');
            })
            .catch(console.error);
        }
    }

    // Handle likes with session management
    async function likePodcast(podcastId) {
        try {
            const response = await fetch(`/like/${podcastId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                const likeBtns = document.querySelectorAll(`[data-podcast-id="${podcastId}"]`);
                likeBtns.forEach(btn => {
                    const likesCount = btn.querySelector('.likes-count');
                    if (likesCount) {
                        likesCount.textContent = data.likes;
                        btn.classList.add('text-red-500');
                        setTimeout(() => {
                            btn.classList.remove('text-red-500');
                        }, 200);
                    }
                });
            } else {
                // Show error toast notification
                showToast(data.error, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showToast('An error occurred while liking the podcast', 'error');
        }
    }

    // Share functionality with social media preview
    async function sharePodcast(podcastId) {
        const shareUrl = `${window.location.origin}/podcast/${podcastId}`;
        try {
            await navigator.clipboard.writeText(shareUrl);
            showToast('Link copied to clipboard!');
        } catch (err) {
            console.error('Error copying link:', err);
            showToast('Failed to copy link', 'error');
        }
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (!activePlayer || e.target.matches('input, textarea')) return;

        switch(e.key) {
            case ' ':
                e.preventDefault();
                activePlayer.playPause();
                break;
            case 'ArrowLeft':
                e.preventDefault();
                activePlayer.skip(-10);
                break;
            case 'ArrowRight':
                e.preventDefault();
                activePlayer.skip(10);
                break;
        }
    });

    // Mobile header adjustment
    function adjustHeaderForMobile() {
        const header = document.querySelector('header');
        if (window.innerWidth <= 768 && header) {
            header.style.paddingTop = '60px';
        } else if (header) {
            header.style.paddingTop = '14px';
        }
    }

    // Initialize
    adjustHeaderForMobile();
    window.addEventListener('resize', adjustHeaderForMobile);

    // Expose functions globally
    window.likePodcast = likePodcast;
    window.sharePodcast = sharePodcast;
    window.updateViewCount = updateViewCount;
    window.embedPodcast = embedPodcast;

    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(uploadForm);
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (response.ok) {
                    alert('Podcast uploaded successfully!');
                    window.location.reload();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error uploading podcast:', error);
                alert('An error occurred while uploading the podcast.');
            }
        });
    }
});

// Add this new function for toast notifications
function showToast(message, type = 'success') {
    // Remove existing toast if present
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }

    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast-notification fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg transform transition-all duration-300 z-50 ${
        type === 'error' ? 'bg-red-500' : 'bg-green-500'
    } text-white`;
    toast.style.transform = 'translateY(100%)';
    toast.style.opacity = '0';
    toast.textContent = message;

    // Add to DOM
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => {
        toast.style.transform = 'translateY(0)';
        toast.style.opacity = '1';
    }, 100);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.transform = 'translateY(100%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add this new function for embedding podcasts
async function embedPodcast(podcastId) {
    const embedCode = `<iframe 
        src="${window.location.origin}/embed/${podcastId}" 
        width="100%" 
        height="160" 
        frameborder="0" 
        allowfullscreen 
        allow="autoplay; clipboard-write; encrypted-media; picture-in-picture">
    </iframe>`;
    
    try {
        await navigator.clipboard.writeText(embedCode);
        showToast('Embed code copied! You can now paste it in your social media post');
    } catch (err) {
        console.error('Error copying embed code:', err);
        showToast('Failed to copy embed code', 'error');
    }
}

// Add to window object
window.embedPodcast = embedPodcast;
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

    // Single source of truth for upload handling
    let isUploading = false;
    const uploadForm = document.getElementById('uploadForm');
    
    if (uploadForm) {
        // Remove any existing event listeners
        uploadForm.replaceWith(uploadForm.cloneNode(true));
        const newUploadForm = document.getElementById('uploadForm');
        const uploadButton = newUploadForm.querySelector('#uploadButton');
        const uploadSpinner = uploadButton.querySelector('.upload-spinner');
        const buttonText = uploadButton.querySelector('span');

        newUploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (isUploading) {
                console.log('Upload already in progress');
                return;
            }

            try {
                isUploading = true;
                uploadButton.disabled = true;
                uploadSpinner.classList.remove('hidden');
                buttonText.textContent = 'Uploading...';

                const formData = new FormData(newUploadForm);
                
                // Add timestamp to prevent duplicate uploads
                formData.append('timestamp', Date.now().toString());

                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    const podcastList = document.getElementById('podcastList');
                    if (podcastList) {
                        const newPodcastElement = createPodcastElement(data);
                        podcastList.insertAdjacentHTML('afterbegin', newPodcastElement);
                    }
                    showAdminToast('Podcast uploaded successfully!', 'success');
                    newUploadForm.reset();
                } else {
                    throw new Error(data.error || 'Upload failed');
                }
            } catch (error) {
                console.error('Upload error:', error);
                showAdminToast(error.message || 'Upload failed', 'error');
            } finally {
                isUploading = false;
                uploadButton.disabled = false;
                uploadSpinner.classList.add('hidden');
                buttonText.textContent = 'Upload Podcast';
            }
        });
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
                activeWavesurfer.pause();
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

        let hasStartedPlaying = false;
        let hasCompletedPlay = false;
        let startTime = 0;
        const podcastId = player.querySelector('[data-view-count]')?.getAttribute('data-view-count');

        // Handle play event
        wavesurfer.on('play', () => {
            activeWavesurfer = wavesurfer;
            if (!hasStartedPlaying && wavesurfer.getCurrentTime() < 1) {
                hasStartedPlaying = true;
                startTime = wavesurfer.getCurrentTime();
            }
        });

        // Handle finish event
        wavesurfer.on('finish', () => {
            playButton.querySelector('.play-icon').classList.remove('hidden');
            playButton.querySelector('.pause-icon').classList.add('hidden');
            activeWavesurfer = null;

            // Only count view if played from near beginning to end
            const duration = wavesurfer.getDuration();
            if (hasStartedPlaying && !hasCompletedPlay && startTime < 1 && podcastId) {
                hasCompletedPlay = true;
                updateViewCount(podcastId);
            }
        });

        // Reset flags when seeking to beginning
        wavesurfer.on('seek', (position) => {
            if (position === 0) {
                hasStartedPlaying = false;
                hasCompletedPlay = false;
                startTime = 0;
            }
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
                // Update all instances of this podcast's view count
                const viewCounts = document.querySelectorAll(`[data-view-count="${podcastId}"]`);
                viewCounts.forEach(viewCount => {
                    viewCount.textContent = `${data.views} plays`;
                });
                localStorage.setItem(viewKey, 'true');
            })
            .catch(console.error);
        }
    }

    // Handle likes with session management
    async function likePodcast(podcastId) {
        // Prevent multiple likes by checking localStorage
        if (likedPodcasts.has(podcastId.toString())) {
            showToast('Already liked this podcast', 'error');
            return;
        }

        try {
            // Disable all like buttons for this podcast immediately
            const likeBtns = document.querySelectorAll(`[data-podcast-id="${podcastId}"]`);
            likeBtns.forEach(btn => {
                btn.disabled = true;
                btn.style.pointerEvents = 'none';
            });

            const response = await fetch(`/like/${podcastId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Add to liked set and save to localStorage
                likedPodcasts.add(podcastId.toString());
                localStorage.setItem('likedPodcasts', JSON.stringify([...likedPodcasts]));

                likeBtns.forEach(btn => {
                    const likesCount = btn.querySelector('.likes-count');
                    if (likesCount) {
                        likesCount.textContent = data.likes;
                        btn.classList.add('text-red-500');
                        // Keep the red color to indicate liked state
                        btn.classList.add('liked');
                    }
                });
            } else {
                // Re-enable buttons if there's an error
                likeBtns.forEach(btn => {
                    btn.disabled = false;
                    btn.style.pointerEvents = 'auto';
                });
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
        if (!activeWavesurfer || e.target.matches('input, textarea')) return;

        switch(e.key) {
            case ' ':
                e.preventDefault();
                const activePlayButton = document.querySelector('.audio-player .play-button');
                if (activePlayButton) {
                    activePlayButton.click();
                }
                break;
            case 'ArrowLeft':
                e.preventDefault();
                if (activeWavesurfer) {
                    activeWavesurfer.skip(-10);
                }
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (activeWavesurfer) {
                    activeWavesurfer.skip(10);
                }
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

    // Initialize like button states
    likedPodcasts.forEach(podcastId => {
        const likeBtns = document.querySelectorAll(`[data-podcast-id="${podcastId}"]`);
        likeBtns.forEach(btn => {
            btn.disabled = true;
            btn.style.pointerEvents = 'none';
            btn.classList.add('text-red-500', 'liked');
        });
    });
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

// Add at the top level, after the DOMContentLoaded listener declaration
function createPodcastElement(podcast) {
    const createdAt = new Date(podcast.created_at);
    const timeAgo = formatTimeAgo(createdAt);

    return `
        <div class="podcast-item bg-black rounded-lg p-4 border border-gray-800" data-podcast-id="${podcast.id}">
            <div class="flex flex-col space-y-2">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-[#A4A5A6] font-medium">${podcast.title}</h3>
                        <span class="text-xs text-gray-500">${timeAgo}</span>
                    </div>
                    <button onclick="deletePodcast(${podcast.id})" class="text-red-500 hover:text-red-600 ml-4">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
}

function formatTimeAgo(date) {
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffTime / (1000 * 60));

    if (diffDays > 365) {
        return `${Math.floor(diffDays / 365)}y ago`;
    } else if (diffDays > 30) {
        return `${Math.floor(diffDays / 30)}mo ago`;
    } else if (diffDays > 0) {
        return `${diffDays}d ago`;
    } else if (diffHours > 0) {
        return `${diffHours}h ago`;
    } else if (diffMinutes > 0) {
        return `${diffMinutes}m ago`;
    }
    return 'just now';
}

// Replace showToast with showAdminToast in the upload form handler
function showAdminToast(message, type = 'success') {
    const toast = document.getElementById('adminToast');
    if (!toast) return;

    toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg transform transition-all duration-300 z-50 ${
        type === 'error' ? 'bg-red-500' : 'bg-green-500'
    } text-white`;
    toast.textContent = message;
    toast.style.transform = 'translateY(0)';
    toast.style.opacity = '1';

    setTimeout(() => {
        toast.style.transform = 'translateY(100%)';
        toast.style.opacity = '0';
    }, 3000);
}

// Add at the beginning of your player.js file, after DOMContentLoaded
const likedPodcasts = new Set(JSON.parse(localStorage.getItem('likedPodcasts') || '[]'));
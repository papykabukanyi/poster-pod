document.addEventListener('DOMContentLoaded', () => {
    // Preloader handling - add null check
    const preloader = document.getElementById('preloader');
    if (preloader) {
        setTimeout(() => {
            preloader.style.opacity = '0';
            setTimeout(() => {
                preloader.style.display = 'none';
            }, 300);
        }, 1500);
    }

    // Single source of truth for upload handling - add null check
    let isUploading = false;
    const uploadForm = document.getElementById('uploadForm');
    
    if (uploadForm) {
        const uploadButton = uploadForm.querySelector('#uploadButton');
        // Only proceed if uploadButton exists
        if (uploadButton) {
            const uploadSpinner = uploadButton.querySelector('.upload-spinner');
            const buttonText = uploadButton.querySelector('span');

            // Add the event listener only if all required elements exist
            uploadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                if (isUploading) {
                    console.log('Upload already in progress');
                    return;
                }

                try {
                    isUploading = true;
                    // Upload logic here...
                } finally {
                    isUploading = false;
                }
            });
        }
    }

    // Initialize players - add null check
    const players = document.querySelectorAll('.audio-player');
    if (players.length === 0) {
        // No players found on this page, exit early
        return;
    }

    let activeWavesurfer = null;
    const wavesurfers = [];
    let currentPlayingIndex = -1;
    const playedInSession = new Set();

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
            const podcastId = player.closest('.rounded-lg').querySelector('[data-view-count]')?.getAttribute('data-view-count');
            
            if (activeWavesurfer && activeWavesurfer !== wavesurfer) {
                activeWavesurfer.pause();
                const activePlayers = document.querySelectorAll('.audio-player');
                activePlayers.forEach(p => {
                    const btn = p.querySelector('.play-button');
                    btn.querySelector('.play-icon').classList.remove('hidden');
                    btn.querySelector('.pause-icon').classList.add('hidden');
                });
            }

            // Check if podcast is not playing and hasn't been played in this session
            if (!wavesurfer.isPlaying() && podcastId && !playedInSession.has(podcastId)) {
                // Update view count immediately before playing
                updateViewCount(podcastId);
                playedInSession.add(podcastId);
            }

            wavesurfer.playPause();
            playButton.querySelector('.play-icon').classList.toggle('hidden');
            playButton.querySelector('.pause-icon').classList.toggle('hidden');
            
            if (wavesurfer.isPlaying()) {
                activeWavesurfer = wavesurfer;
                currentPlayingIndex = index;
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
            
            // Remove this podcast from playedInSession when it finishes
            // This allows for a new view count when replayed
            const podcastId = player.closest('.rounded-lg').querySelector('[data-view-count]')?.getAttribute('data-view-count');
            if (podcastId) {
                playedInSession.delete(podcastId);
            }
            
            const nextIndex = (currentPlayingIndex + 1) % players.length;
            const nextPlayer = players[nextIndex];
            const nextWavesurfer = wavesurfers[nextIndex];
            const nextPlayButton = nextPlayer.querySelector('.play-button');
            const nextPodcastId = nextPlayer.closest('.rounded-lg').querySelector('[data-view-count]')?.getAttribute('data-view-count');

            if (nextWavesurfer) {
                // Reset current player
                activeWavesurfer = null;
                currentPlayingIndex = nextIndex;

                // Update view count before playing next
                if (!playedInSession.has(nextPodcastId) && nextPodcastId) {
                    updateViewCount(nextPodcastId);
                    playedInSession.add(nextPodcastId);
                }

                // Start next player
                nextWavesurfer.play();
                nextPlayButton.querySelector('.play-icon').classList.add('hidden');
                nextPlayButton.querySelector('.pause-icon').classList.remove('hidden');
                activeWavesurfer = nextWavesurfer;
            }
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

        let playTimer = null;
        let totalPlayTime = 0;
        const PLAY_COUNT_INTERVAL = 30; // 30 seconds

        // Handle play event with 30-second intervals
        wavesurfer.on('play', () => {
            activeWavesurfer = wavesurfer;
            if (!playTimer) {
                playTimer = setInterval(() => {
                    totalPlayTime += 30;
                    if (totalPlayTime >= 30 && podcastId) {
                        updateViewCount(podcastId);
                    }
                }, PLAY_COUNT_INTERVAL * 1000);
            }
        });

        // Handle pause and finish events
        wavesurfer.on('pause', () => {
            if (playTimer) {
                clearInterval(playTimer);
                playTimer = null;
            }
        });

        wavesurfer.on('finish', () => {
            if (playTimer) {
                clearInterval(playTimer);
                playTimer = null;
            }
            totalPlayTime = 0;
        });

        wavesurfer.on('ready', () => {
            const audioProcessing = initializeAudioProcessing(wavesurfer);
            
            // Add processing controls
            const controls = document.createElement('div');
            controls.className = 'audio-processing-controls flex items-center space-x-2 mt-2';
            controls.innerHTML = `
                <div class="flex items-center">
                    <label class="text-xs text-[#A4A5A6] mr-2">Bass</label>
                    <input type="range" class="bass-control w-16" min="0" max="15" value="7" step="0.1">
                </div>
                <div class="flex items-center">
                    <label class="text-xs text-[#A4A5A6] mr-2">Power</label>
                    <input type="range" class="power-control w-16" min="0" max="2" value="1" step="0.1">
                </div>
            `;

            // Add visualization canvas
            const containerDiv = document.createElement('div');
            containerDiv.style.position = 'relative';
            containerDiv.appendChild(audioProcessing.canvas);
            container.appendChild(containerDiv);

            // Add controls after waveform
            container.appendChild(controls);

            // Control handlers
            const bassControl = controls.querySelector('.bass-control');
            bassControl.addEventListener('input', (e) => {
                audioProcessing.bassBoost.gain.value = parseFloat(e.target.value);
            });

            const powerControl = controls.querySelector('.power-control');
            powerControl.addEventListener('input', (e) => {
                audioProcessing.gainNode.gain.value = parseFloat(e.target.value);
            });

            // Preset profiles
            const presets = {
                normal: {
                    bass: 7,
                    power: 1
                },
                bassBoost: {
                    bass: 12,
                    power: 1.4
                },
                superBass: {
                    bass: 15,
                    power: 1.7
                }
            };

            // Add preset selector
            const presetSelect = document.createElement('select');
            presetSelect.className = 'bg-black text-[#A4A5A6] text-xs ml-2 p-1 rounded';
            presetSelect.innerHTML = `
                <option value="normal">Normal</option>
                <option value="bassBoost">Bass Boost</option>
                <option value="superBass">Super Bass</option>
            `;

            presetSelect.addEventListener('change', (e) => {
                const preset = presets[e.target.value];
                audioProcessing.bassBoost.gain.value = preset.bass;
                audioProcessing.gainNode.gain.value = preset.power;
                bassControl.value = preset.bass;
                powerControl.value = preset.power;
            });

            controls.appendChild(presetSelect);
        });
    });

    // Update view count
    function updateViewCount(podcastId) {
        // Update UI immediately
        const viewCounts = document.querySelectorAll(`[data-view-count="${podcastId}"]`);
        viewCounts.forEach(viewCount => {
            const currentViews = parseInt(viewCount.textContent);
            viewCount.textContent = `${currentViews + 1} plays`;
        });

        // Send request to server
        fetch(`/views/${podcastId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            // Update with server count if different
            if (data.views) {
                viewCounts.forEach(viewCount => {
                    viewCount.textContent = `${data.views} plays`;
                });
            }
        })
        .catch(console.error);
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
        style="border: 0; width: 100%; height: 120px; border-radius: 8px;"
        title="Poster Podcast Player"
        allow="autoplay; clipboard-write; encrypted-media; picture-in-picture"
        loading="lazy">
    </iframe>`;
    
    try {
        await navigator.clipboard.writeText(embedCode);
        showToast('Embed code copied! Ready to paste anywhere');
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

// Add these at the top level, after the DOMContentLoaded listener declaration
let currentPlayingIndex = -1;
const playedInSession = new Set();

const initializeAudioProcessing = (wavesurfer) => {
    // Get Web Audio API context
    const audioContext = wavesurfer.backend.ac;
    
    // Create audio nodes
    const sourceNode = wavesurfer.backend.mediaElementSource;
    const analyzerNode = audioContext.createAnalyser();
    const bassBoost = audioContext.createBiquadFilter();
    const compressor = audioContext.createDynamicsCompressor();
    const gainNode = audioContext.createGain();

    // Configure bass boost
    bassBoost.type = 'lowshelf';
    bassBoost.frequency.value = 100; // Adjust frequency range for bass
    bassBoost.gain.value = 7; // Boost bass by 7dB

    // Configure compressor for richer sound
    compressor.threshold.value = -24;
    compressor.knee.value = 30;
    compressor.ratio.value = 12;
    compressor.attack.value = 0.003;
    compressor.release.value = 0.25;

    // Configure analyzer
    analyzerNode.fftSize = 2048;
    const bufferLength = analyzerNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    // Create processing chain
    sourceNode
        .connect(bassBoost)
        .connect(compressor)
        .connect(gainNode)
        .connect(analyzerNode)
        .connect(audioContext.destination);

    // Add visualization canvas 
    const canvas = document.createElement('canvas');
    canvas.width = 200;
    canvas.height = 40;
    canvas.style.position = 'absolute';
    canvas.style.bottom = '0';
    canvas.style.left = '0';
    canvas.style.opacity = '0.5';
    canvas.style.pointerEvents = 'none';

    const canvasCtx = canvas.getContext('2d');
    
    // Visualization function
    const drawVisual = () => {
        requestAnimationFrame(drawVisual);
        analyzerNode.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = 'rgb(0, 0, 0)';
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for(let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i] / 2;
            canvasCtx.fillStyle = `rgb(${barHeight + 100},50,50)`;
            canvasCtx.fillRect(x, canvas.height - barHeight/2, barWidth, barHeight);
            x += barWidth + 1;
        }
    };

    drawVisual();

    return {
        bassBoost,
        compressor,
        gainNode,
        canvas
    };
};
// Remove the direct import and use CDN
const WaveformPath = window.WaveformPath;

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
    let activePlayer = null;
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
        
        // Define gradients
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height * 1.35);
        gradient.addColorStop(0, '#656666');
        gradient.addColorStop(0.7, '#656666');
        gradient.addColorStop(0.7, '#ffffff');
        gradient.addColorStop(0.72, '#B1B1B1');
        gradient.addColorStop(1, '#B1B1B1');

        const progressGradient = ctx.createLinearGradient(0, 0, 0, canvas.height * 1.35);
        progressGradient.addColorStop(0, '#EE772F');
        progressGradient.addColorStop(0.7, '#EB4926');
        progressGradient.addColorStop(0.7, '#ffffff');
        progressGradient.addColorStop(0.72, '#F6B094');
        progressGradient.addColorStop(1, '#F6B094');

        // Initialize WaveSurfer
        const wavesurfer = WaveSurfer.create({
            container: container,
            waveColor: '#A4A5A6',
            progressColor: '#4a4a4a',
            url: audio.src,
            height: 40,
            barWidth: 2,
            barGap: 1,
            barRadius: 3
        });

        wavesurfers.push(wavesurfer);

        // Handle play button click
        playButton.addEventListener('click', () => {
            if (activePlayer && activePlayer !== wavesurfer) {
                activePlayer.pause();
                const activeIndex = wavesurfers.indexOf(activePlayer);
                if (activeIndex !== -1) {
                    updatePlayIcon(activeIndex, false);
                }
            }
            wavesurfer.playPause();
            activePlayer = wavesurfer;
        });

        // Handle volume changes
        volumeSlider.addEventListener('input', (e) => {
            wavesurfer.setVolume(parseFloat(e.target.value));
        });

        // Update play button state
        wavesurfer.on('play', () => {
            updatePlayIcon(index, true);
            activePlayer = wavesurfer;
        });

        wavesurfer.on('pause', () => {
            updatePlayIcon(index, false);
        });

        wavesurfer.on('finish', () => {
            updatePlayIcon(index, false);
            activePlayer = null;
        });
    });

    // Helper function to update play icon
    function updatePlayIcon(index, isPlaying) {
        const playButton = document.querySelectorAll('.play-button')[index];
        if (playButton) {
            const playIcon = playButton.querySelector('.play-icon');
            const pauseIcon = playButton.querySelector('.pause-icon');
            if (playIcon && pauseIcon) {
                playIcon.style.display = isPlaying ? 'none' : 'block';
                pauseIcon.style.display = isPlaying ? 'block' : 'none';
            }
        }
    }

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
            
            if (response.ok) {
                const data = await response.json();
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
            } else if (response.status === 400) {
                console.log('Already liked this podcast');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    // Share functionality with social media preview
    function sharePodcast(podcastId) {
        const shareUrl = `${window.location.origin}/podcast/${podcastId}`;
        
        if (navigator.share) {
            navigator.share({
                title: document.title,
                text: 'Check out this podcast!',
                url: shareUrl
            }).catch(console.error);
        } else {
            navigator.clipboard.writeText(shareUrl).then(() => {
                const notification = document.getElementById('shareNotification');
                if (notification) {
                    notification.classList.add('share-notification-show');
                    setTimeout(() => {
                        notification.classList.remove('share-notification-show');
                    }, 3000);
                }
            });
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
});
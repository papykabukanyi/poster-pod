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

        // Play/pause on click
        playButton.addEventListener('click', () => {
            wavesurfer.playPause();
            playButton.querySelector('.play-icon').classList.toggle('hidden');
            playButton.querySelector('.pause-icon').classList.toggle('hidden');
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
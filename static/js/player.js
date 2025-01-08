document.addEventListener('DOMContentLoaded', () => {
    // Preloader animation
    setTimeout(() => {
        const preloader = document.getElementById('preloader');
        if (preloader) {
            preloader.style.opacity = '0';
            preloader.style.transition = 'opacity 0.3s ease';
            setTimeout(() => {
                preloader.style.display = 'none';
            }, 300);
        }
    }, 1500);

    // Initialize WaveSurfer for all audio players
    const players = document.querySelectorAll('.plyr');
    let activePlayer = null;
    const wavesurfers = [];

    players.forEach((player, index) => {
        // Create waveform container
        const waveformContainer = document.createElement('div');
        waveformContainer.className = 'waveform-container';
        player.parentElement.appendChild(waveformContainer);

        // Initialize WaveSurfer
        const wavesurfer = WaveSurfer.create({
            container: waveformContainer,
            waveColor: '#4a5568',
            progressColor: '#ffffff',
            cursorColor: '#718096',
            barWidth: 2,
            barHeight: 1,
            responsive: true,
            height: 40,
            barGap: 2,
            normalize: true,
            interact: true
        });

        // Load audio
        const audioSource = player.querySelector('source').src;
        wavesurfer.load(audioSource);
        wavesurfers.push(wavesurfer);

        // Handle play/pause
        wavesurfer.on('play', () => {
            if (activePlayer && activePlayer !== wavesurfer) {
                activePlayer.pause();
            }
            activePlayer = wavesurfer;
            updatePlayIcon(index, true);
        });

        wavesurfer.on('pause', () => {
            updatePlayIcon(index, false);
        });

        // Update localStorage with current time
        wavesurfer.on('audioprocess', () => {
            localStorage.setItem(`podcast-${audioSource}`, wavesurfer.getCurrentTime());
        });

        // Resume from last position
        wavesurfer.on('ready', () => {
            const lastPosition = localStorage.getItem(`podcast-${audioSource}`);
            if (lastPosition) {
                wavesurfer.setCurrentTime(parseFloat(lastPosition));
            }
        });

        // Handle play button click
        const playButton = player.parentElement.querySelector('.play-button');
        if (playButton) {
            playButton.addEventListener('click', () => {
                wavesurfer.playPause();
            });
        }
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
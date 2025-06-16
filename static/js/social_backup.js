// static/js/social_backup.js
// JavaScript backup for Twitter posting and news fetching
// Used if the Python backend fails

// Global configuration
const config = {
    // Update intervals
    newsCheckInterval: 30 * 60 * 1000, // 30 minutes
    twitterPostInterval: 30 * 60 * 1000, // 30 minutes
    
    // API endpoints 
    newsApiUrl: 'https://newsdata.io/api/1/news',
    newsApiKey: '', // To be set from server-side 
    
    // Timestamps
    lastNewsUpdate: null,
    lastTwitterPost: null,
    
    // Cached data
    cachedNews: null
};

// Initialize system
function initSocialBackup() {
    console.log('Initializing social backup system...');
    
    // Get API key from data attribute
    const scriptTag = document.getElementById('social-backup-script');
    if (scriptTag) {
        config.newsApiKey = scriptTag.getAttribute('data-news-api-key');
    }
    
    // Check if primary systems are working first
    checkPrimarySystemStatus()
        .then(status => {
            if (!status.twitterWorking || !status.newsWorking) {
                console.log('Primary systems unavailable, activating backup');
                startBackupSystems();
            } else {
                console.log('Primary systems operational');
            }
        })
        .catch(err => {
            console.error('Error checking primary systems:', err);
            // Assume failure and start backup
            startBackupSystems();
        });
}

// Check if primary Python backend systems are working
async function checkPrimarySystemStatus() {
    try {
        const response = await fetch('/api/system/status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            return await response.json();
        } else {
            return { 
                twitterWorking: false, 
                newsWorking: false 
            };
        }
    } catch (err) {
        console.error('Error checking primary systems:', err);
        return { 
            twitterWorking: false, 
            newsWorking: false 
        };
    }
}

// Start backup systems
function startBackupSystems() {
    // Start news fetching
    fetchNews();
    setInterval(fetchNews, config.newsCheckInterval);
    
    // Start Twitter posting
    setTimeout(() => {
        postToTwitter();
        setInterval(postToTwitter, config.twitterPostInterval);
    }, 2000); // Initial delay
    
    console.log('Backup systems activated');
}

// Fetch news and update page
async function fetchNews() {
    try {
        if (!config.newsApiKey) {
            console.error('No News API key available');
            return false;
        }
        
        console.log('Fetching news...');
        
        // Add timestamp to prevent caching
        const timestamp = new Date().getTime();
        
        const params = new URLSearchParams({
            apikey: config.newsApiKey,
            country: 'us,gb',
            language: 'en', 
            category: 'top',
            size: 10,
            timestamp: timestamp
        });
        
        const response = await fetch(`${config.newsApiUrl}?${params}`);
        
        if (!response.ok) {
            throw new Error(`News API returned ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.results || data.results.length === 0) {
            console.warn('No news articles found');
            return false;
        }
        
        // Process news articles
        const articles = data.results
            .filter(article => article.title && article.description && article.link)
            .sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));
            
        if (articles.length === 0) {
            console.warn('No valid articles found');
            return false;
        }
        
        // Cache the articles
        config.cachedNews = {
            breaking: articles[0],
            other: articles.slice(1, 6),
            lastUpdate: new Date()
        };
        
        // Update news on page
        updateNewsOnPage(config.cachedNews);
        
        console.log(`Fetched ${articles.length} news articles`);
        config.lastNewsUpdate = new Date();
        
        return true;
    } catch (err) {
        console.error('Error fetching news:', err);
        return false;
    }
}

// Update news on the page
function updateNewsOnPage(newsData) {
    try {
        // Update breaking news
        const breakingNews = document.querySelector('.breaking-news');
        if (breakingNews && newsData.breaking) {
            const article = newsData.breaking;
            
            // Update title and link
            const title = breakingNews.querySelector('h2 a');
            if (title) {
                title.textContent = article.title;
                title.href = article.link;
            }
            
            // Update description
            const description = breakingNews.querySelector('.description');
            if (description) {
                description.textContent = article.description;
            }
            
            // Update image if available
            const image = breakingNews.querySelector('img');
            if (image && article.image_url) {
                image.src = article.image_url;
                image.alt = article.title;
            }
        }
        
        // Update other news
        const otherNewsContainer = document.querySelector('.news-list');
        if (otherNewsContainer && newsData.other && newsData.other.length > 0) {
            // Clear existing items
            otherNewsContainer.innerHTML = '';
            
            // Add new items
            newsData.other.forEach(article => {
                const newsItem = document.createElement('div');
                newsItem.className = 'news-item';
                
                const html = `
                    <h3><a href="${article.link}" target="_blank">${article.title}</a></h3>
                    <p class="description">${article.description}</p>
                    <div class="meta">
                        <span class="source">${article.source_id}</span>
                        <span class="date">${new Date(article.pubDate).toLocaleDateString()}</span>
                    </div>
                `;
                
                newsItem.innerHTML = html;
                otherNewsContainer.appendChild(newsItem);
            });
        }
    } catch (err) {
        console.error('Error updating news on page:', err);
    }
}

// Post to Twitter via backend proxy
async function postToTwitter() {
    try {
        if (!config.cachedNews || !config.cachedNews.breaking) {
            console.warn('No news available to tweet');
            await fetchNews();
            if (!config.cachedNews || !config.cachedNews.breaking) {
                return false;
            }
        }
        
        console.log('Attempting to post to Twitter...');
        
        // Use article from cached news
        const article = config.cachedNews.breaking;
        
        // Generate tweet text
        const tweetText = generateTweetText(article);
        
        // Call backend proxy to post to Twitter
        const response = await fetch('/api/tweet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: tweetText
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Twitter post successful:', result);
            config.lastTwitterPost = new Date();
            return true;
        } else {
            console.error('Twitter post failed:', await response.text());
            return false;
        }
    } catch (err) {
        console.error('Error posting to Twitter:', err);
        return false;
    }
}

// Generate tweet text
function generateTweetText(article) {
    // Get title (max 120 chars)
    const title = article.title ? article.title.substring(0, 120) : 'Breaking News';
    
    // Format with URL on new line to prevent auto-thumbnails
    return `${title}...\n\n#BreakingNews #News\n\nhttps://www.onposter.site/news`;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on pages where this should run
    if (document.querySelector('.news-container')) {
        setTimeout(initSocialBackup, 3000); // Delay to let main systems start first
    }
});

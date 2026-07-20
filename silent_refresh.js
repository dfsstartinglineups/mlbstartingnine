// The Silent Refresh Engine
setInterval(() => {
    // Fetch the live index.html page, bypassing the browser cache
    fetch(window.location.href, { cache: "no-store" })
        .then(response => response.text())
        .then(html => {
            // Parse the incoming HTML into a virtual DOM
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');
            
            // Swap the HTML of the main data containers silently
            const containers = ['yesterday-container', 'today-container', 'tomorrow-container'];
            containers.forEach(id => {
                const liveContainer = document.getElementById(id);
                const freshContainer = newDoc.getElementById(id);
                
                if (liveContainer && freshContainer) {
                    liveContainer.innerHTML = freshContainer.innerHTML;
                }
            });
        })
        .catch(error => console.error('Silent refresh failed:', error));
}, 30000); // 30,000 ms = 30 seconds to match your original script

// Main JavaScript file for Tower of Temptation PvP Statistics Bot
document.addEventListener('DOMContentLoaded', function() {
    console.log('PvP Stats Bot Dashboard Loaded');
    
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Initialize popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    
    // Initialize feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
    
    // Add animation classes on scroll
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    
    if (animatedElements.length > 0) {
        const animateOnScroll = function() {
            animatedElements.forEach(element => {
                const elementTop = element.getBoundingClientRect().top;
                const elementVisible = 150;
                
                if (elementTop < window.innerHeight - elementVisible) {
                    element.classList.add('fade-in');
                }
            });
        };
        
        // Run once on page load
        animateOnScroll();
        
        // Run on scroll
        window.addEventListener('scroll', animateOnScroll);
    }
    
    // Auto-refresh status data
    const statusSection = document.querySelector('#status-refresh');
    if (statusSection) {
        const refreshStatus = async () => {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update online status
                const statusBadge = document.querySelector('#bot-status-badge');
                if (statusBadge) {
                    if (data.online) {
                        statusBadge.innerHTML = '<i data-feather="check-circle"></i> Online';
                        statusBadge.className = 'badge bg-success rounded-pill p-2';
                    } else {
                        statusBadge.innerHTML = '<i data-feather="x-circle"></i> Offline';
                        statusBadge.className = 'badge bg-danger rounded-pill p-2';
                    }
                }
                
                // Update uptime
                const uptimeElement = document.querySelector('#bot-uptime');
                if (uptimeElement) {
                    const hours = Math.floor(data.uptime / 3600);
                    const minutes = Math.floor((data.uptime % 3600) / 60);
                    const seconds = data.uptime % 60;
                    uptimeElement.textContent = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
                
                // Update guilds count
                const guildsElement = document.querySelector('#bot-guilds');
                if (guildsElement) {
                    guildsElement.textContent = data.guilds;
                }
                
                // Update timestamp
                const timestampElement = document.querySelector('#bot-last-update');
                if (timestampElement) {
                    const date = new Date(data.last_update);
                    timestampElement.textContent = date.toLocaleString();
                }
                
                // Reinitialize feather icons after DOM updates
                if (typeof feather !== 'undefined') {
                    feather.replace();
                }
            } catch (error) {
                console.error('Error fetching status data:', error);
            }
        };
        
        // Refresh every 30 seconds
        setInterval(refreshStatus, 30000);
    }
    
    // Handle status page chart updates
    const statsChartElement = document.getElementById('statsChart');
    if (statsChartElement) {
        const refreshChartData = async () => {
            try {
                const response = await fetch('/api/stats?days=1');
                const data = await response.json();
                
                if (data.length > 0 && window.statsChart) {
                    // Prepare data for chart
                    const timestamps = data.map(stat => {
                        const date = new Date(stat.timestamp);
                        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    });
                    
                    const commandData = data.map(stat => stat.commands_used);
                    const userData = data.map(stat => stat.active_users);
                    const killsData = data.map(stat => stat.kills_tracked);
                    
                    // Update chart data
                    window.statsChart.data.labels = timestamps;
                    window.statsChart.data.datasets[0].data = commandData;
                    window.statsChart.data.datasets[1].data = userData;
                    window.statsChart.data.datasets[2].data = killsData;
                    
                    window.statsChart.update();
                }
            } catch (error) {
                console.error('Error fetching chart data:', error);
            }
        };
        
        // If the chart exists on the page, update it periodically
        if (typeof Chart !== 'undefined' && statsChartElement) {
            // Refresh every 60 seconds
            setInterval(refreshChartData, 60000);
        }
    }
    
    // Toggle animation for feature icons
    const featureIcons = document.querySelectorAll('.feature-icon');
    featureIcons.forEach(icon => {
        icon.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.2)';
        });
        
        icon.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });
});

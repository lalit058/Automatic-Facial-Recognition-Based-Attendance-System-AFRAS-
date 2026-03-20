// sidebar.js - Complete Sidebar Functionality

class SidebarManager {
    constructor() {
        this.sidebar = document.getElementById('sidebar');
        this.overlay = document.getElementById('sidebarOverlay');
        this.mobileBtn = document.getElementById('mobileMenuBtn');
        this.toggleBtn = document.querySelector('.sidebar-toggle');
        this.main = document.querySelector('main');
        this.isMobile = window.innerWidth <= 768;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadSavedState();
        this.setupTooltips();
        this.autoDismissMessages();
        
        // Initial check
        this.handleResize();
    }
    
    bindEvents() {
        // Mobile menu button
        if (this.mobileBtn) {
            this.mobileBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMobileSidebar();
            });
        }
        
        // Desktop toggle button
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDesktopSidebar();
            });
        }
        
        // Overlay click
        if (this.overlay) {
            this.overlay.addEventListener('click', () => {
                this.closeMobileSidebar();
            });
        }
        
        // Window resize with debounce
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 100);
        });
        
        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.handleEscapeKey();
            }
        });
        
        // Close mobile sidebar when clicking a nav link
        if (this.sidebar) {
            const navLinks = this.sidebar.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    if (window.innerWidth <= 768) {
                        this.closeMobileSidebar();
                    }
                });
            });
        }
    }
    
    toggleMobileSidebar() {
        if (!this.sidebar || !this.overlay) return;
        
        const isActive = this.sidebar.classList.contains('active');
        
        if (isActive) {
            this.closeMobileSidebar();
        } else {
            this.openMobileSidebar();
        }
    }
    
    openMobileSidebar() {
        this.sidebar.classList.add('active');
        this.overlay.classList.add('active');
        document.body.classList.add('sidebar-open'); // Prevent body scroll
        
        // Update icon
        if (this.mobileBtn) {
            const icon = this.mobileBtn.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-times';
            }
        }
    }
    
    closeMobileSidebar() {
        this.sidebar.classList.remove('active');
        this.overlay.classList.remove('active');
        document.body.classList.remove('sidebar-open'); // Restore body scroll
        
        // Update icon
        if (this.mobileBtn) {
            const icon = this.mobileBtn.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-bars';
            }
        }
    }
    
    toggleDesktopSidebar() {
        this.sidebar.classList.toggle('collapsed');
        
        // Update toggle icon with smooth rotation
        const toggleIcon = this.toggleBtn?.querySelector('i');
        if (toggleIcon) {
            toggleIcon.style.transform = this.sidebar.classList.contains('collapsed') ? 
                'rotate(180deg)' : 'rotate(0deg)';
        }
        
        // Save state
        localStorage.setItem('sidebarCollapsed', this.sidebar.classList.contains('collapsed'));
        
        // Update main content class
        if (this.main) {
            if (this.sidebar.classList.contains('collapsed')) {
                this.main.classList.add('expanded');
            } else {
                this.main.classList.remove('expanded');
            }
        }
    }
    
    handleResize() {
        this.isMobile = window.innerWidth <= 768;
        
        if (this.isMobile) {
            // Mobile mode - drawer behavior (sidebar slides over content)
            this.sidebar.classList.remove('collapsed');
            this.closeMobileSidebar();
            
            if (this.main) {
                this.main.classList.remove('expanded');
            }
            
            // Reset toggle icon rotation
            const toggleIcon = this.toggleBtn?.querySelector('i');
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        } else {
            // Desktop mode - sidebar pushes content
            this.loadSavedState();
            
            // Ensure mobile sidebar is closed
            this.closeMobileSidebar();
        }
    }
    
    loadSavedState() {
        if (window.innerWidth <= 768) return;
        
        const savedState = localStorage.getItem('sidebarCollapsed');
        const shouldBeCollapsed = savedState === 'true';
        
        if (shouldBeCollapsed) {
            this.sidebar.classList.add('collapsed');
            if (this.main) this.main.classList.add('expanded');
            
            const toggleIcon = this.toggleBtn?.querySelector('i');
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(180deg)';
            }
        } else {
            this.sidebar.classList.remove('collapsed');
            if (this.main) this.main.classList.remove('expanded');
            
            const toggleIcon = this.toggleBtn?.querySelector('i');
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        }
    }
    
    handleEscapeKey() {
        if (window.innerWidth <= 768 && this.sidebar?.classList.contains('active')) {
            this.closeMobileSidebar();
        }
    }
    
    setupTooltips() {
        if (!this.sidebar) return;
        
        const setupTooltipEvents = (element, tooltipSelector) => {
            if (!element) return;
            
            const tooltip = element.querySelector(tooltipSelector);
            if (!tooltip) return;
            
            element.addEventListener('mouseenter', () => {
                if (this.sidebar.classList.contains('collapsed') && window.innerWidth > 768) {
                    tooltip.style.opacity = '1';
                    tooltip.style.visibility = 'visible';
                    tooltip.style.transform = 'translateY(-50%) scale(1)';
                }
            });
            
            element.addEventListener('mouseleave', () => {
                tooltip.style.opacity = '0';
                tooltip.style.visibility = 'hidden';
                tooltip.style.transform = 'translateY(-50%) scale(0.95)';
            });
        };
        
        // Setup tooltips for nav links
        const navLinks = this.sidebar.querySelectorAll('.nav-link');
        navLinks.forEach(link => setupTooltipEvents(link, '.nav-tooltip'));
        
        // Setup tooltip for profile
        const profile = this.sidebar.querySelector('.user-profile');
        setupTooltipEvents(profile, '.profile-tooltip');
        
        // Setup tooltip for logout
        const logout = this.sidebar.querySelector('.logout-btn');
        setupTooltipEvents(logout, '.logout-tooltip');
    }
    
    autoDismissMessages() {
        const messages = document.querySelectorAll('.msg[data-auto-dismiss="true"]');
        
        messages.forEach((msg, index) => {
            if (msg.dataset.timerSet) return;
            
            msg.dataset.timerSet = 'true';
            
            setTimeout(() => {
                msg.style.animation = 'slideUp 0.4s ease-out forwards';
                
                setTimeout(() => {
                    if (msg.parentNode) msg.remove();
                }, 400);
            }, 5000 + (index * 300));
        });
    }
}

// Add slideUp animation if not present
const style = document.createElement('style');
style.textContent = `
    @keyframes slideUp {
        from {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
        to {
            opacity: 0;
            transform: translateY(-20px) scale(0.95);
        }
    }
`;
document.head.appendChild(style);

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.sidebarManager = new SidebarManager();
});
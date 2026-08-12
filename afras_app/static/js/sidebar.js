// sidebar.js - Complete Sidebar Functionality

class SidebarManager {
    constructor() {
        this.sidebar = null;
        this.overlay = null;
        this.mobileBtn = null;
        this.toggleBtn = null;
        this.main = null;
        this.isMobile = false;
        this.updateTimeout = null;
        this.lastUpdateTime = 0;
        this.isInitialized = false;

        this.init();
    }

    init() {
        // Get elements
        this.sidebar = document.getElementById('sidebar');
        this.overlay = document.getElementById('sidebarOverlay');
        this.mobileBtn = document.getElementById('mobileMenuBtn');
        this.toggleBtn = document.querySelector('.sidebar-toggle');
        this.main = document.querySelector('main');

        // Check if we have required elements
        if (!this.sidebar) {
            console.warn('Sidebar element not found');
            return;
        }

        this.isMobile = window.innerWidth <= 768;

        this.bindEvents();
        this.loadSavedState();
        this.setupTooltips();
        this.autoDismissMessages();

        // Initial layout update
        setTimeout(() => {
            this.handleResize();
            this.updateMainLayout();
        }, 100);

        this.isInitialized = true;
    }

    bindEvents() {
        // Mobile menu button click
        if (this.mobileBtn) {
            this.mobileBtn.removeEventListener('click', this.mobileClickHandler);
            this.mobileClickHandler = this.toggleMobileSidebar.bind(this);
            this.mobileBtn.addEventListener('click', this.mobileClickHandler);
        } else {
            console.warn('Mobile menu button not found');
        }

        // Desktop toggle button click
        if (this.toggleBtn) {
            this.toggleBtn.removeEventListener('click', this.toggleClickHandler);
            this.toggleClickHandler = this.toggleDesktopSidebar.bind(this);
            this.toggleBtn.addEventListener('click', this.toggleClickHandler);
        }

        // Overlay click
        if (this.overlay) {
            this.overlay.removeEventListener('click', this.overlayClickHandler);
            this.overlayClickHandler = this.closeMobileSidebar.bind(this);
            this.overlay.addEventListener('click', this.overlayClickHandler);
        }

        // Window resize
        let resizeTimeout;
        window.removeEventListener('resize', this.resizeHandler);
        this.resizeHandler = () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
                this.updateMainLayout();
            }, 150);
        };
        window.addEventListener('resize', this.resizeHandler);

        // Escape key
        document.removeEventListener('keydown', this.escapeHandler);
        this.escapeHandler = (e) => {
            if (e.key === 'Escape') {
                this.handleEscapeKey();
            }
        };
        document.addEventListener('keydown', this.escapeHandler);

        // Close mobile sidebar on nav link click
        if (this.sidebar) {
            const navLinks = this.sidebar.querySelectorAll('.nav-link');
            navLinks.forEach((link) => {
                link.removeEventListener('click', this.navLinkClickHandler);
                this.navLinkClickHandler = () => {
                    if (window.innerWidth <= 768) {
                        this.closeMobileSidebar();
                    }
                };
                link.addEventListener('click', this.navLinkClickHandler);
            });
        }
    }

    updateMainLayout() {
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }

        this.updateTimeout = setTimeout(() => {
            this._performLayoutUpdate();
        }, 50);
    }

    _performLayoutUpdate() {
        if (!this.main) return;

        this.lastUpdateTime = Date.now();

        const isMobile = window.innerWidth <= 768;
        const isCollapsed = this.sidebar ? this.sidebar.classList.contains('collapsed') : false;

        if (isMobile) {
            this.main.style.marginLeft = '0';
            this.main.style.width = '100%';
            this.main.style.paddingTop = '40px';
        } else {
            this.main.style.paddingTop = '0.5rem';
            const sidebarWidth = getComputedStyle(document.documentElement)
                .getPropertyValue(isCollapsed ? '--sidebar-collapsed' : '--sidebar-width').trim();

            const widthValue = sidebarWidth || (isCollapsed ? '70px' : '215px');
            this.main.style.marginLeft = widthValue;
            this.main.style.width = `calc(100% - ${widthValue})`;
        }

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('sidebarLayoutChanged', {
            detail: {
                isMobile: isMobile,
                isCollapsed: isCollapsed
            }
        }));
    }

    toggleMobileSidebar() {
        if (!this.sidebar || !this.overlay) {
            console.warn('Cannot toggle mobile sidebar: missing elements');
            return;
        }

        const isActive = this.sidebar.classList.contains('active');

        if (isActive) {
            this.closeMobileSidebar();
        } else {
            this.openMobileSidebar();
        }
    }

    openMobileSidebar() {
        if (!this.sidebar || !this.overlay) return;

        this.sidebar.classList.add('active');
        this.overlay.classList.add('active');
        document.body.classList.add('sidebar-open');

        // Change mobile button icon
        if (this.mobileBtn) {
            const icon = this.mobileBtn.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-times';
            }
        }

        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }

    closeMobileSidebar() {
        if (!this.sidebar || !this.overlay) return;

        this.sidebar.classList.remove('active');
        this.overlay.classList.remove('active');
        document.body.classList.remove('sidebar-open');

        // Restore body scroll
        document.body.style.overflow = '';

        // Change mobile button icon back
        if (this.mobileBtn) {
            const icon = this.mobileBtn.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-bars';
            }
        }
    }

    toggleDesktopSidebar() {
        if (!this.sidebar) return;

        this.sidebar.classList.toggle('collapsed');

        const toggleIcon = this.toggleBtn ? this.toggleBtn.querySelector('i') : null;
        if (toggleIcon) {
            if (this.sidebar.classList.contains('collapsed')) {
                toggleIcon.style.transform = 'rotate(180deg)';
            } else {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        }

        // Save state
        localStorage.setItem('sidebarCollapsed', this.sidebar.classList.contains('collapsed'));

        // Update main class
        if (this.main) {
            if (this.sidebar.classList.contains('collapsed')) {
                this.main.classList.add('expanded');
            } else {
                this.main.classList.remove('expanded');
            }
        }

        this.updateMainLayout();
    }

    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth <= 768;

        if (this.isMobile) {
            // On mobile, ensure collapsed is removed and sidebar is closed
            if (this.sidebar) {
                this.sidebar.classList.remove('collapsed');
            }
            this.closeMobileSidebar();

            if (this.main) {
                this.main.classList.remove('expanded');
            }

            const toggleIcon = this.toggleBtn ? this.toggleBtn.querySelector('i') : null;
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        } else if (wasMobile && !this.isMobile) {
            // Switching from mobile to desktop
            this.loadSavedState();
            this.closeMobileSidebar();
            document.body.style.overflow = '';
        }

        this.updateMainLayout();
    }

    loadSavedState() {
        // Don't load saved state on mobile
        if (window.innerWidth <= 768) return;

        const savedState = localStorage.getItem('sidebarCollapsed');
        const shouldBeCollapsed = savedState === 'true';

        if (shouldBeCollapsed) {
            this.sidebar.classList.add('collapsed');
            if (this.main) this.main.classList.add('expanded');

            const toggleIcon = this.toggleBtn ? this.toggleBtn.querySelector('i') : null;
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(180deg)';
            }
        } else {
            this.sidebar.classList.remove('collapsed');
            if (this.main) this.main.classList.remove('expanded');

            const toggleIcon = this.toggleBtn ? this.toggleBtn.querySelector('i') : null;
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        }

        this.updateMainLayout();
    }

    handleEscapeKey() {
        if (window.innerWidth <= 768 && this.sidebar && this.sidebar.classList.contains('active')) {
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
                if (this.sidebar && this.sidebar.classList.contains('collapsed') && window.innerWidth > 768) {
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

        const navLinks = this.sidebar.querySelectorAll('.nav-link');
        navLinks.forEach((link) => {
            setupTooltipEvents(link, '.nav-tooltip');
        });

        const profile = this.sidebar.querySelector('.user-profile');
        setupTooltipEvents(profile, '.profile-tooltip');

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

// Initialize sidebar when DOM is ready
if (!window.sidebarManagerInstance) {
    document.addEventListener('DOMContentLoaded', function() {
        window.sidebarManagerInstance = new SidebarManager();
    });
}

// Also try to initialize immediately if DOM is already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        if (!window.sidebarManagerInstance) {
            window.sidebarManagerInstance = new SidebarManager();
        }
    });
} else {
    if (!window.sidebarManagerInstance) {
        window.sidebarManagerInstance = new SidebarManager();
    }
}
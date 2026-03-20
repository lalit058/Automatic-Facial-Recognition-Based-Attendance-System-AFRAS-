// Immediately create the photoModal object with zoom and download functionality
window.photoModal = {
    currentZoom: 1,
    maxZoom: 3,
    minZoom: 0.5,
    zoomStep: 0.25,
    currentPhotoUrl: '',
    currentFileName: '',
    translateX: 0,
    translateY: 0,
    isDragging: false,

    open: function (imageSrc, title = '', subtitle = '') {
        // Store current photo info for download
        this.currentPhotoUrl = imageSrc;
        this.currentFileName = `${title.replace(/\s+/g, '_')}.jpg`;

        // Create modal if it doesn't exist
        let modal = document.getElementById('photoModal');
        if (!modal) {
            this.createModal();
            modal = document.getElementById('photoModal');
            
            if (!modal) {
                console.error('Failed to create photo modal');
                return;
            }
        }

        // Set image source
        const modalImg = document.getElementById('modalImage');
        if (modalImg && imageSrc) {
            modalImg.src = imageSrc;
            modalImg.alt = title;
            modalImg.onload = () => {
                // Reset zoom when new image is loaded
                this.resetZoom();
            };
        }

        // Set title and subtitle
        const modalTitle = document.getElementById('modalTitle');
        const modalSubtitle = document.getElementById('modalSubtitle');

        if (modalTitle) modalTitle.textContent = title;
        if (modalSubtitle) modalSubtitle.textContent = subtitle;

        // Show modal
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        
        // Reset transform values
        this.translateX = 0;
        this.translateY = 0;
        
        // Update zoom display
        this.updateZoomDisplay();
        this.updateZoomButtons();
    },

    close: function () {
        const modal = document.getElementById('photoModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
            this.resetZoom();
        }
    },

    zoomIn: function () {
        if (this.currentZoom < this.maxZoom) {
            this.currentZoom += this.zoomStep;
            this.applyZoom();
            this.updateZoomButtons();
        }
    },

    zoomOut: function () {
        if (this.currentZoom > this.minZoom) {
            this.currentZoom -= this.zoomStep;
            this.applyZoom();
            this.updateZoomButtons();
        }
    },

    resetZoom: function () {
        this.currentZoom = 1;
        this.translateX = 0;
        this.translateY = 0;
        this.applyZoom();
        this.updateZoomButtons();
    },

    applyZoom: function () {
        const modalImg = document.getElementById('modalImage');
        if (modalImg) {
            modalImg.style.transform = `scale(${this.currentZoom}) translate(${this.translateX}px, ${this.translateY}px)`;
            modalImg.style.transition = 'transform 0.3s ease';
        }
        this.updateZoomDisplay();
    },

    updateZoomDisplay: function () {
        const zoomDisplay = document.getElementById('zoomLevelDisplay');
        if (zoomDisplay) {
            zoomDisplay.textContent = `${Math.round(this.currentZoom * 100)}%`;
        }
    },

    updateZoomButtons: function () {
        // Use setTimeout to ensure DOM elements are available
        setTimeout(() => {
            const zoomInBtn = document.getElementById('zoomInBtn');
            const zoomOutBtn = document.getElementById('zoomOutBtn');
            const resetZoomBtn = document.getElementById('resetZoomBtn');

            if (zoomInBtn) {
                zoomInBtn.disabled = this.currentZoom >= this.maxZoom;
                zoomInBtn.style.opacity = zoomInBtn.disabled ? '0.5' : '1';
                zoomInBtn.style.cursor = zoomInBtn.disabled ? 'not-allowed' : 'pointer';
            }

            if (zoomOutBtn) {
                zoomOutBtn.disabled = this.currentZoom <= this.minZoom;
                zoomOutBtn.style.opacity = zoomOutBtn.disabled ? '0.5' : '1';
                zoomOutBtn.style.cursor = zoomOutBtn.disabled ? 'not-allowed' : 'pointer';
            }

            if (resetZoomBtn) {
                resetZoomBtn.disabled = this.currentZoom === 1;
                resetZoomBtn.style.opacity = resetZoomBtn.disabled ? '0.5' : '1';
                resetZoomBtn.style.cursor = resetZoomBtn.disabled ? 'not-allowed' : 'pointer';
            }
        }, 50);
    },

    downloadImage: function () {
        if (!this.currentPhotoUrl) return;

        const link = document.createElement('a');
        link.href = this.currentPhotoUrl;
        link.download = this.currentFileName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Optional: Show success message
        console.log('Image downloaded successfully!');
    },

    createModal: function () {
        // Remove existing modal if any
        const existingModal = document.getElementById('photoModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Create new modal with zoom controls and download button
        const modalHTML = `
            <div id="photoModal" class="photo-modal-overlay" style="display: none;">
                <div class="photo-modal-container">
                    <!-- Top Controls -->
                    <div class="photo-controls">
                        <button class="photo-control-btn" onclick="window.photoModal.zoomOut()" title="Zoom Out" id="zoomOutBtn">
                            <i class="fas fa-search-minus"></i>
                        </button>
                        <button class="photo-control-btn" onclick="window.photoModal.resetZoom()" title="Reset Zoom" id="resetZoomBtn">
                            <i class="fas fa-search"></i>
                        </button>
                        <button class="photo-control-btn" onclick="window.photoModal.zoomIn()" title="Zoom In" id="zoomInBtn">
                            <i class="fas fa-search-plus"></i>
                        </button>
                        <button class="photo-control-btn download-btn" onclick="window.photoModal.downloadImage()" title="Download Image">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="photo-control-btn close-btn" onclick="window.photoModal.close()" title="Close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    
                    <!-- Image Container -->
                    <div class="photo-modal-image-container" id="photoImageContainer">
                        <img id="modalImage" class="photo-modal-image" draggable="false">
                    </div>
                    
                    <!-- Caption -->
                    <div class="photo-modal-caption">
                        <h3 id="modalTitle"></h3>
                        <p id="modalSubtitle"></p>
                        <div class="photo-info">
                            <span>Zoom: <span id="zoomLevelDisplay">100%</span></span>
                            <span class="separator">|</span>
                            <span>Use mouse wheel to zoom</span>
                            <span class="separator">|</span>
                            <span>Drag to pan when zoomed</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Add click outside to close
        const modal = document.getElementById('photoModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.close();
                }
            });
        }

        // Add wheel zoom to the image
        const modalImg = document.getElementById('modalImage');
        const container = document.getElementById('photoImageContainer');
        
        if (modalImg) {
            modalImg.addEventListener('wheel', (e) => {
                e.preventDefault();
                if (e.deltaY < 0) {
                    this.zoomIn();
                } else {
                    this.zoomOut();
                }
            });

            // Add drag to pan when zoomed
            modalImg.addEventListener('mousedown', (e) => {
                if (this.currentZoom > 1) {
                    this.isDragging = true;
                    this.startX = e.clientX - this.translateX;
                    this.startY = e.clientY - this.translateY;
                    modalImg.style.cursor = 'grabbing';
                }
            });

            document.addEventListener('mousemove', (e) => {
                if (!this.isDragging) return;
                e.preventDefault();
                this.translateX = e.clientX - this.startX;
                this.translateY = e.clientY - this.startY;
                modalImg.style.transform = `scale(${this.currentZoom}) translate(${this.translateX}px, ${this.translateY}px)`;
            });

            document.addEventListener('mouseup', () => {
                this.isDragging = false;
                if (modalImg) {
                    modalImg.style.cursor = this.currentZoom > 1 ? 'grab' : 'default';
                }
            });

            modalImg.addEventListener('mouseleave', () => {
                this.isDragging = false;
                if (modalImg) {
                    modalImg.style.cursor = this.currentZoom > 1 ? 'grab' : 'default';
                }
            });
        }

        // Update zoom buttons state
        this.updateZoomButtons();

        // Keyboard events
        document.addEventListener('keydown', (e) => {
            const modal = document.getElementById('photoModal');
            if (modal && modal.style.display === 'flex') {
                if (e.key === 'Escape') {
                    this.close();
                } else if (e.key === '+' || e.key === '=') {
                    e.preventDefault();
                    this.zoomIn();
                } else if (e.key === '-' || e.key === '_') {
                    e.preventDefault();
                    this.zoomOut();
                } else if (e.key === '0') {
                    e.preventDefault();
                    this.resetZoom();
                }
            }
        });

        // Initial update of zoom buttons
        this.updateZoomButtons();
    }
};

// Initialize modal based on ready state
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.photoModal.createModal();
    });
} else {
    window.photoModal.createModal();
}

// For very fast clicks, also try to create modal immediately
setTimeout(function() {
    if (!document.getElementById('photoModal')) {
        window.photoModal.createModal();
    }
}, 0);
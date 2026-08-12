// ========== PHOTO MODAL - FULLY FUNCTIONAL ==========

(function() {
    'use strict';

    let currentZoom = 1;
    let maxZoom = 3;
    let minZoom = 0.5;
    let zoomStep = 0.25;
    let currentPhotoUrl = '';
    let currentFileName = '';
    let translateX = 0;
    let translateY = 0;
    let isDragging = false;
    let startX = 0,
        startY = 0;

    // Create modal on load
    function createModal() {
        // Remove existing modal if any
        const existingModal = document.getElementById('photoModal');
        if (existingModal) {
            existingModal.remove();
        }

        const modalHTML = `
            <div id="photoModal" class="photo-modal-overlay" style="display: none;">
                <div class="photo-modal-container">
                    <div class="photo-controls">
                        <button class="photo-control-btn" id="zoomOutBtn" title="Zoom Out">
                            <i class="fas fa-search-minus"></i>
                        </button>
                        <button class="photo-control-btn" id="resetZoomBtn" title="Reset Zoom">
                            <i class="fas fa-search"></i>
                        </button>
                        <button class="photo-control-btn" id="zoomInBtn" title="Zoom In">
                            <i class="fas fa-search-plus"></i>
                        </button>
                        <button class="photo-control-btn download-btn" id="downloadPhotoBtn" title="Download Image">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="photo-control-btn close-btn" id="closePhotoBtn" title="Close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="photo-modal-image-container" id="photoImageContainer">
                        <img id="modalImage" class="photo-modal-image" draggable="false" style="transform: scale(1);">
                    </div>
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
        attachEventListeners();
    }

    function attachEventListeners() {
        const modal = document.getElementById('photoModal');
        const zoomInBtn = document.getElementById('zoomInBtn');
        const zoomOutBtn = document.getElementById('zoomOutBtn');
        const resetZoomBtn = document.getElementById('resetZoomBtn');
        const downloadBtn = document.getElementById('downloadPhotoBtn');
        const closeBtn = document.getElementById('closePhotoBtn');
        const modalImg = document.getElementById('modalImage');
        const container = document.getElementById('photoImageContainer');

        if (!modal) return;

        // Close on overlay click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });

        if (zoomInBtn) zoomInBtn.addEventListener('click', zoomIn);
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', zoomOut);
        if (resetZoomBtn) resetZoomBtn.addEventListener('click', resetZoom);
        if (downloadBtn) downloadBtn.addEventListener('click', downloadImage);
        if (closeBtn) closeBtn.addEventListener('click', closeModal);

        if (modalImg) {
            // Wheel zoom
            modalImg.addEventListener('wheel', function(e) {
                e.preventDefault();
                if (e.deltaY < 0) {
                    zoomIn();
                } else {
                    zoomOut();
                }
            });

            // Drag to pan
            modalImg.addEventListener('mousedown', startDrag);
            document.addEventListener('mousemove', onDrag);
            document.addEventListener('mouseup', stopDrag);

            modalImg.addEventListener('mouseleave', stopDrag);
        }

        // Keyboard events
        document.addEventListener('keydown', function(e) {
            if (modal.style.display !== 'flex') return;

            switch (e.key) {
                case 'Escape':
                    closeModal();
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    zoomIn();
                    break;
                case '-':
                case '_':
                    e.preventDefault();
                    zoomOut();
                    break;
                case '0':
                    e.preventDefault();
                    resetZoom();
                    break;
            }
        });
    }

    function startDrag(e) {
        const modalImg = document.getElementById('modalImage');
        if (currentZoom > 1 && modalImg) {
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            modalImg.style.cursor = 'grabbing';
            e.preventDefault();
        }
    }

    function onDrag(e) {
        if (!isDragging) return;
        const modalImg = document.getElementById('modalImage');
        if (modalImg) {
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            modalImg.style.transform = `scale(${currentZoom}) translate(${translateX}px, ${translateY}px)`;
        }
    }

    function stopDrag() {
        isDragging = false;
        const modalImg = document.getElementById('modalImage');
        if (modalImg) {
            modalImg.style.cursor = currentZoom > 1 ? 'grab' : 'default';
        }
    }

    function applyZoom() {
        const modalImg = document.getElementById('modalImage');
        if (modalImg) {
            modalImg.style.transform = `scale(${currentZoom}) translate(${translateX}px, ${translateY}px)`;
        }
        updateZoomDisplay();
        updateButtonsState();
    }

    function updateZoomDisplay() {
        const display = document.getElementById('zoomLevelDisplay');
        if (display) {
            display.textContent = `${Math.round(currentZoom * 100)}%`;
        }
    }

    function updateButtonsState() {
        const zoomInBtn = document.getElementById('zoomInBtn');
        const zoomOutBtn = document.getElementById('zoomOutBtn');
        const resetZoomBtn = document.getElementById('resetZoomBtn');

        if (zoomInBtn) {
            zoomInBtn.disabled = currentZoom >= maxZoom;
            zoomInBtn.style.opacity = currentZoom >= maxZoom ? '0.5' : '1';
        }
        if (zoomOutBtn) {
            zoomOutBtn.disabled = currentZoom <= minZoom;
            zoomOutBtn.style.opacity = currentZoom <= minZoom ? '0.5' : '1';
        }
        if (resetZoomBtn) {
            resetZoomBtn.disabled = currentZoom === 1;
            resetZoomBtn.style.opacity = currentZoom === 1 ? '0.5' : '1';
        }
    }

    function zoomIn() {
        if (currentZoom < maxZoom) {
            currentZoom += zoomStep;
            if (currentZoom > maxZoom) currentZoom = maxZoom;
            applyZoom();
        }
    }

    function zoomOut() {
        if (currentZoom > minZoom) {
            currentZoom -= zoomStep;
            if (currentZoom < minZoom) currentZoom = minZoom;
            applyZoom();
        }
    }

    function resetZoom() {
        currentZoom = 1;
        translateX = 0;
        translateY = 0;
        applyZoom();
    }

    function downloadImage() {
        if (!currentPhotoUrl) return;

        const link = document.createElement('a');
        link.href = currentPhotoUrl;
        link.download = currentFileName || 'profile-photo.jpg';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Show feedback (optional)
        console.log('Image downloaded:', currentFileName);
    }

    function closeModal() {
        const modal = document.getElementById('photoModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
            resetZoom();
        }
    }

    // Public API
    window.photoModal = {
        open: function(imageSrc, title = '', subtitle = '') {
            // Ensure modal exists
            let modal = document.getElementById('photoModal');
            if (!modal) {
                createModal();
                modal = document.getElementById('photoModal');
                if (!modal) {
                    console.error('Failed to create photo modal');
                    return;
                }
            }

            // Reset state
            currentZoom = 1;
            translateX = 0;
            translateY = 0;
            currentPhotoUrl = imageSrc;
            currentFileName = `${(title || 'photo').replace(/\s+/g, '_')}.jpg`;

            // Set image
            const modalImg = document.getElementById('modalImage');
            if (modalImg) {
                modalImg.src = imageSrc;
                modalImg.alt = title;
                modalImg.style.transform = 'scale(1) translate(0px, 0px)';
                modalImg.style.cursor = 'grab';
            }

            // Set title and subtitle
            const modalTitle = document.getElementById('modalTitle');
            const modalSubtitle = document.getElementById('modalSubtitle');
            if (modalTitle) modalTitle.textContent = title;
            if (modalSubtitle) modalSubtitle.textContent = subtitle;

            // Show modal
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';

            // Update UI
            updateZoomDisplay();
            updateButtonsState();
        },

        close: closeModal,

        // For backward compatibility with your sidebar
        createModal: createModal
    };

    // Auto-create modal on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            createModal();
        });
    } else {
        createModal();
    }
})();
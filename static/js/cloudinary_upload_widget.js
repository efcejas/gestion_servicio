/**
 * Cloudinary Upload Widget for Video Files
 * Implementa subida directa de videos a Cloudinary sin pasar por el servidor Django
 * Evita timeouts de Heroku (H28) para archivos grandes
 */

// Configuración global
const CLOUDINARY_CONFIG = {
    cloudName: window.CLOUDINARY_CLOUD_NAME || '', // Definido en template
    uploadPreset: window.CLOUDINARY_UPLOAD_PRESET || 'clases_residentes_unsigned',
    folder: 'clases_residentes/videos',
    resourceType: 'video',
    maxFileSize: 500000000, // 500 MB
    maxVideoDuration: 3600, // 60 minutos
};

/**
 * Inicializa el widget de Cloudinary para subida de videos
 */
function initCloudinaryVideoWidget() {
    const uploadBtn = document.getElementById('upload-video-btn');
    const videoProgressContainer = document.getElementById('video-upload-progress');
    const videoProgressBar = document.getElementById('video-progress-bar');
    const videoProgressText = document.getElementById('video-progress-text');
    const videoPreviewContainer = document.getElementById('video-preview-container');
    const videoPublicIdInput = document.getElementById('id_archivo_video_public_id');
    const archivoVideoInput = document.getElementById('id_archivo_video');
    
    if (!uploadBtn) return;

    // Crear widget de Cloudinary
    const widget = cloudinary.createUploadWidget(
        {
            cloudName: CLOUDINARY_CONFIG.cloudName,
            uploadPreset: CLOUDINARY_CONFIG.uploadPreset,
            folder: CLOUDINARY_CONFIG.folder,
            resourceType: CLOUDINARY_CONFIG.resourceType,
            maxFileSize: CLOUDINARY_CONFIG.maxFileSize,
            maxVideoDuration: CLOUDINARY_CONFIG.maxVideoDuration,
            clientAllowedFormats: ['mp4', 'mov', 'avi', 'wmv', 'flv', 'mkv', 'm4v', 'webm'],
            sources: ['local', 'url', 'camera'],
            showAdvancedOptions: false,
            cropping: false,
            multiple: false,
            defaultSource: 'local',
            styles: {
                palette: {
                    window: "#FFFFFF",
                    windowBorder: "#2563EB",
                    tabIcon: "#2563EB",
                    menuIcons: "#5A616A",
                    textDark: "#000000",
                    textLight: "#FFFFFF",
                    link: "#2563EB",
                    action: "#2563EB",
                    inactiveTabIcon: "#9CA3AF",
                    error: "#EF4444",
                    inProgress: "#2563EB",
                    complete: "#10B981",
                    sourceBg: "#F9FAFB"
                },
                fonts: {
                    default: null,
                    "'Inter', sans-serif": {
                        url: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
                        active: true
                    }
                }
            },
            text: {
                "es": {
                    "or": "o",
                    "back": "Atrás",
                    "advanced": "Avanzado",
                    "close": "Cerrar",
                    "no_results": "Sin resultados",
                    "search_placeholder": "Buscar archivos",
                    "about_uw": "Acerca del widget",
                    "max_file_size": "Tamaño máximo: 500 MB",
                    "max_video_duration": "Duración máxima: 60 minutos",
                    "unsave_video_warn": "¿Seguro que quieres cerrar? El video no se guardará.",
                    "menu": {
                        "files": "Mis archivos",
                        "web": "dirección web",
                        "camera": "Cámara"
                    },
                    "drag_and_drop": {
                        "title": "Arrastra tu video aquí",
                        "description": "o"
                    },
                    "select_file_btn": "Seleccionar video",
                    "upload_more": "Subir más",
                    "done": "Listo",
                    "local": {
                        "browse": "Examinar",
                        "dd_title_single": "Arrastra un archivo aquí",
                        "dd_title_multi": "Arrastra archivos aquí",
                        "drop_title_single": "Suelta el archivo para subir",
                        "drop_title_multiple": "Suelta los archivos para subir"
                    },
                    "queue": {
                        "title": "Cola de subida",
                        "title_uploading_with_counter": "Subiendo {{num}} archivo",
                        "title_uploading_processing_with_counter": "Subiendo {{num}} archivo, procesando {{processed}}",
                        "done": "Listo",
                        "failed": "Falló",
                        "abort": "Cancelar",
                        "abort_all": "Cancelar todo",
                        "remove": "Eliminar",
                        "remove_all": "Eliminar todo"
                    }
                }
            },
            language: 'es',
        },
        (error, result) => {
            if (error) {
                console.error('Error en widget de Cloudinary:', error);
                showError('Error al subir el video. Por favor, intenta nuevamente.');
                hideProgress();
                return;
            }

            // Manejar eventos
            if (result.event === 'queues-start') {
                showProgress();
            }

            if (result.event === 'upload-added') {
                updateProgress(0, 'Preparando subida...');
            }

            if (result.event === 'upload-progress') {
                const percent = Math.round((result.data.bytes result.data.total_bytes) * 100);
                updateProgress(percent, `Subiendo: ${percent}%`);
            }

            if (result.event === 'success') {
                const { public_id, secure_url, resource_type, format, duration, bytes } = result.info;
                
                console.log('Video subido exitosamente:', public_id);
                
                // Guardar public_id en el campo oculto
                if (videoPublicIdInput) {
                    videoPublicIdInput.value = public_id;
                }
                
                // Guardar en el campo archivo_video también (formato Cloudinary)
                if (archivoVideoInput) {
                    archivoVideoInput.value = `video/upload/${public_id}`;
                }
                
                // Mostrar preview
                showVideoPreview(secure_url, public_id, formatBytes(bytes), formatDuration(duration));
                
                updateProgress(100, '✓ Video subido correctamente');
                
                setTimeout(() => {
                    hideProgress();
                }, 2000);
            }

            if (result.event === 'abort') {
                hideProgress();
            }
        }
    );

    // Evento click en botón de subir
    uploadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        widget.open();
    });

    // Funciones helper
    function showProgress() {
        if (videoProgressContainer) {
            videoProgressContainer.classList.remove('hidden');
        }
    }

    function hideProgress() {
        if (videoProgressContainer) {
            videoProgressContainer.classList.add('hidden');
        }
    }

    function updateProgress(percent, text) {
        if (videoProgressBar) {
            videoProgressBar.style.width = `${percent}%`;
            videoProgressBar.setAttribute('aria-valuenow', percent);
        }
        if (videoProgressText) {
            videoProgressText.textContent = text;
        }
    }

    function showVideoPreview(url, publicId, size, duration) {
        if (videoPreviewContainer) {
            videoPreviewContainer.innerHTML = `
                <div class="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <div class="flex items-start gap-3">
                        <svg class="w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <div class="flex-1">
                            <h4 class="text-sm font-semibold text-green-900 mb-2">✓ Video cargado exitosamente</h4>
                            <video controls class="w-full max-w-md rounded-lg mb-2">
                                <source src="${url}" type="video/mp4">
                                Tu navegador no soporta el tag de video.
                            </video>
                            <div class="text-xs text-green-700 space-y-1">
                                <p><strong>Tamaño:</strong> ${size}</p>
                                <p><strong>Duración:</strong> ${duration}</p>
                                <p class="text-xs text-gray-500 mt-1">ID: ${publicId}</p>
                            </div>
                        </div>
                        <button type="button" onclick="removeVideo()" class="text-red-600 hover:text-red-800">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
        }
    }

    function showError(message) {
        // Mostrar mensaje de error (puedes personalizarlo)
        alert(message);
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    function formatDuration(seconds) {
        if (!seconds) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Función global para eliminar video
window.removeVideo = function() {
    const videoPublicIdInput = document.getElementById('id_archivo_video_public_id');
    const archivoVideoInput = document.getElementById('id_archivo_video');
    const videoPreviewContainer = document.getElementById('video-preview-container');
    
    if (videoPublicIdInput) videoPublicIdInput.value = '';
    if (archivoVideoInput) archivoVideoInput.value = '';
    if (videoPreviewContainer) videoPreviewContainer.innerHTML = '';
    
    // Marcar para eliminación si es edición
    const eliminarVideoInput = document.getElementById('eliminar-video');
    if (eliminarVideoInput) eliminarVideoInput.value = '1';
};

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCloudinaryVideoWidget);
} else {
    initCloudinaryVideoWidget();
}

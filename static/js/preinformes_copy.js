(function(window) {
    function notifyDefault(message, type) {
        if (type === 'error') {
            window.alert(message);
        }
    }

    function copyPlainTextFallback(text, notify) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        textarea.setSelectionRange(0, textarea.value.length);

        try {
            if (!document.execCommand('copy')) {
                throw new Error('execCommand falló');
            }
            notify('¡Informe copiado en texto plano para NetTerm!', 'success');
            return true;
        } catch (error) {
            notify('Error al copiar al portapapeles', 'error');
            return false;
        } finally {
            document.body.removeChild(textarea);
        }
    }

    function copyPlainText(text, notify) {
        // Evita las limitaciones del mecanismo legacy con informes extensos.
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text)
                .then(() => {
                    notify('¡Informe copiado en texto plano para NetTerm!', 'success');
                    return true;
                })
                .catch((error) => {
                    console.error('Error con Clipboard.writeText:', error);
                    return copyPlainTextFallback(text, notify);
                });
        }

        return Promise.resolve(copyPlainTextFallback(text, notify));
    }

    function copyHtmlWithFallback(htmlContent, plainText, notify) {
        const tempDiv = document.createElement('div');
        tempDiv.contentEditable = 'true';
        tempDiv.style.position = 'fixed';
        tempDiv.style.left = '-9999px';
        tempDiv.style.fontWeight = 'normal';
        tempDiv.style.fontStyle = 'normal';
        tempDiv.style.textDecoration = 'none';
        tempDiv.innerHTML = htmlContent;
        document.body.appendChild(tempDiv);

        try {
            const range = document.createRange();
            range.selectNodeContents(tempDiv);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);

            if (document.execCommand('copy')) {
                notify('¡Informe copiado con formato!', 'success');
            } else {
                throw new Error('execCommand falló');
            }
        } catch (error) {
            console.error('Error con fallback HTML:', error);
            copyPlainText(plainText, notify);
        } finally {
            document.body.removeChild(tempDiv);
            window.getSelection().removeAllRanges();
        }
    }

    function copyFinalReport(options) {
        const preinformeId = options.preinformeId;
        const defaultSistemaDestino = options.defaultSistemaDestino || 'eges';
        const notify = options.notify || notifyDefault;

        return fetch(`/preinformes/copiar-informe/${preinformeId}/`)
            .then((response) => response.json())
            .then((data) => {
                if (!data.informe_html) {
                    notify('No se pudo obtener el informe', 'error');
                    return false;
                }

                const sistemaDestino = data.sistema_destino || defaultSistemaDestino;
                if (sistemaDestino === 'netterm') {
                    return copyPlainText(data.informe_texto || '', notify);
                }

                const htmlContent = data.informe_html;
                const plainText = data.informe_texto || data.informe_final || '';

                if (navigator.clipboard && window.ClipboardItem) {
                    try {
                        const htmlBlob = new Blob([htmlContent], { type: 'text/html' });
                        const textBlob = new Blob([plainText], { type: 'text/plain' });
                        const clipboardItem = new ClipboardItem({
                            'text/html': htmlBlob,
                            'text/plain': textBlob
                        });

                        return navigator.clipboard.write([clipboardItem])
                            .then(() => {
                                notify('¡Informe copiado con formato para EGES!', 'success');
                                return true;
                            })
                            .catch((error) => {
                                console.error('Error con ClipboardItem:', error);
                                copyHtmlWithFallback(htmlContent, plainText, notify);
                                return true;
                            });
                    } catch (error) {
                        console.error('Error creando ClipboardItem:', error);
                        copyHtmlWithFallback(htmlContent, plainText, notify);
                        return true;
                    }
                }

                copyHtmlWithFallback(htmlContent, plainText, notify);
                return true;
            })
            .catch((error) => {
                console.error('Error al obtener informe:', error);
                notify('Error al obtener el informe', 'error');
                return false;
            });
    }

    window.PreinformesCopy = {
        copyFinalReport: copyFinalReport,
        copyHtmlWithFallback: copyHtmlWithFallback,
        copyPlainText: copyPlainText,
    };
})(window);

(function(window) {
    const DISABLE_ID = 'preinformes-netterm-literal-hyphens';

    function replaceHorizontalRules(editor) {
        const currentData = editor.getData();
        const literalData = currentData.replace(/<hr\b[^>]*>/gi, '<p>------</p>');
        if (literalData !== currentData) {
            editor.setData(literalData);
        }
    }

    function updatePlainTextView(editor, sourceElement, isNetterm) {
        const editableElement = editor.ui && editor.ui.getEditableElement
            ? editor.ui.getEditableElement()
            : null;
        if (editableElement) {
            editableElement.classList.toggle(
                'preinformes-netterm-plain',
                isNetterm
            );
        }
        if (sourceElement && sourceElement.parentElement) {
            sourceElement.parentElement.classList.toggle(
                'preinformes-netterm-plain-container',
                isNetterm
            );
        }
    }

    function configureEditor(editor, sourceElement, isNetterm) {
        updatePlainTextView(editor, sourceElement, isNetterm);
        if (!editor || !editor.plugins || !editor.plugins.has('Autoformat')) {
            return;
        }

        const autoformat = editor.plugins.get('Autoformat');
        if (isNetterm) {
            autoformat.forceDisabled(DISABLE_ID);
            replaceHorizontalRules(editor);
        } else {
            autoformat.clearForceDisabled(DISABLE_ID);
        }
    }

    function bind(options) {
        const editorId = options.editorId;
        const systemField = options.systemFieldId
            ? document.getElementById(options.systemFieldId)
            : null;
        const sourceElement = document.getElementById(editorId);
        let editorInstance = null;
        let normalizationScheduled = false;
        let hintElement = null;

        function isNetterm() {
            const currentSystem = systemField
                ? systemField.value
                : options.fixedSystem;
            return currentSystem === 'netterm';
        }

        function apply(editor) {
            editorInstance = editor;
            if (!hintElement && sourceElement) {
                const editorWrapper = sourceElement.nextElementSibling;
                if (editorWrapper) {
                    hintElement = document.createElement('p');
                    hintElement.className = 'preinformes-netterm-hint';
                    hintElement.textContent = 'Vista NetTerm: cada renglón visible se copiará como un renglón. Para dejar un espacio, agregá un renglón vacío real.';
                    editorWrapper.insertAdjacentElement('afterend', hintElement);
                }
            }
            configureEditor(editorInstance, sourceElement, isNetterm());
            if (hintElement) {
                hintElement.hidden = !isNetterm();
            }
            editorInstance.model.document.on('change:data', function() {
                if (!isNetterm() || normalizationScheduled) {
                    return;
                }
                normalizationScheduled = true;
                window.setTimeout(function() {
                    normalizationScheduled = false;
                    replaceHorizontalRules(editorInstance);
                }, 0);
            });
        }

        if (window.editors && window.editors[editorId]) {
            apply(window.editors[editorId]);
        } else if (window.ckeditorRegisterCallback) {
            window.ckeditorRegisterCallback(editorId, apply);
        }

        if (systemField) {
            systemField.addEventListener('change', function() {
                if (editorInstance) {
                    configureEditor(editorInstance, sourceElement, isNetterm());
                    if (hintElement) {
                        hintElement.hidden = !isNetterm();
                    }
                }
            });
        }
    }

    window.PreinformesNettermEditor = {
        bind: bind,
    };
})(window);

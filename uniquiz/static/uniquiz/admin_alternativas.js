document.addEventListener('DOMContentLoaded', () => {
    const group = document.querySelector('#alternativa_set-group');
    if (!group) return;

    const header = group.querySelector('thead tr');
    const correctHeader = header?.querySelector('th.column-correta');
    const deleteHeader = header?.lastElementChild;
    if (header && correctHeader && deleteHeader && !header.querySelector('.alternativa-edit-header')) {
        const editHeader = document.createElement('th');
        editHeader.className = 'alternativa-edit-header';
        editHeader.textContent = 'Editar';
        header.insertBefore(editHeader, correctHeader);
        header.insertBefore(deleteHeader, correctHeader);
    }

    const iconButton = (icon, title, className) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `alternativa-action ${className}`;
        button.title = title;
        button.setAttribute('aria-label', title);
        const image = document.createElement('img');
        image.src = `/static/admin/img/${icon}`;
        image.alt = '';
        button.appendChild(image);
        return button;
    };

    function configure(row) {
        if (row.dataset.configured) return;
        const text = row.querySelector('[name$="-texto"]');
        const remove = row.querySelector('[name$="-DELETE"]');
        const removeCell = row.querySelector('td.delete');
        if (!text || !removeCell) return;
        row.dataset.configured = 'true';

        // O nome em negrito é a representação __str__ do objeto, duplicada pelo campo.
        row.querySelectorAll('td.original p').forEach(el => el.hidden = true);

        const display = document.createElement('span');
        display.className = 'alternativa-display';
        display.textContent = text.value;
        text.insertAdjacentElement('afterend', display);
        text.hidden = true;

        const edit = iconButton('icon-changelink.svg', 'Editar alternativa', 'alternativa-edit');
        const confirmEdit = document.createElement('button');
        confirmEdit.type = 'button';
        confirmEdit.textContent = '✓';
        confirmEdit.className = 'alternativa-confirm';
        confirmEdit.title = 'Confirmar edição';
        confirmEdit.hidden = true;
        const editCell = document.createElement('td');
        editCell.className = 'alternativa-edit-cell';
        editCell.append(edit, confirmEdit);
        const correctCell = row.querySelector('td.field-correta');
        if (correctCell) {
            row.insertBefore(editCell, correctCell);
            row.insertBefore(removeCell, correctCell);
        } else {
            row.insertBefore(editCell, removeCell);
        }

        edit.onclick = () => {
            display.hidden = true;
            edit.hidden = true;
            text.hidden = false;
            confirmEdit.hidden = false;
            text.focus();
        };
        confirmEdit.onclick = () => {
            if (!text.value.trim()) {
                alert('O texto da alternativa não pode ficar vazio.');
                text.focus();
                return;
            }
            text.value = text.value.trim();
            display.textContent = text.value;
            text.hidden = true;
            display.hidden = false;
            edit.hidden = false;
            confirmEdit.hidden = true;
        };

        if (remove) {
            const removeLabel = remove.closest('label');
            if (removeLabel) removeLabel.hidden = true;
            else remove.hidden = true;
        }

        const deleteButton = iconButton('icon-deletelink.svg', 'Remover alternativa', 'alternativa-delete');
        removeCell.appendChild(deleteButton);
        deleteButton.onclick = () => {
            if (window.confirm('Marcar esta alternativa para remoção? A mudança só será gravada ao salvar.')) {
                if (remove) {
                    remove.checked = true;
                    row.hidden = true;
                } else {
                    // Linhas ainda não salvas são removidas do formulário pelo controle nativo do Django.
                    row.querySelector('.inline-deletelink')?.click();
                }
            }
        };
    }

    const configureAll = () => group.querySelectorAll('tr.form-row:not(.empty-form)').forEach(configure);
    configureAll();
    new MutationObserver(configureAll).observe(group, { childList: true, subtree: true });
});

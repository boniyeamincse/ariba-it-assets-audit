(() => {
    const sidebar = document.getElementById('portal-sidebar');
    const desktopHome = document.getElementById('portal-sidebar-home');
    const mobileDialog = document.getElementById('portal-mobile-navigation');
    const mobileOpen = document.querySelector('[data-open-mobile]');
    const command = document.querySelector('[data-command-dialog]');
    const closePopovers = (exception = null) => {
        document.querySelectorAll('.portal-popover[open]').forEach((popover) => {
            if (popover !== exception) popover.open = false;
        });
    };

    for (const popover of document.querySelectorAll('.portal-popover')) {
        popover.addEventListener('toggle', () => {
            if (popover.open) closePopovers(popover);
        });
        popover.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && popover.open) {
                popover.open = false;
                popover.querySelector('summary').focus();
            }
        });
    }
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.portal-popover')) closePopovers();
    });

    if (!sidebar) return;

    const collapse = sidebar.querySelector('[data-sidebar-collapse]');
    const storageKey = `portal-sidebar:${sidebar.dataset.account}`;
    const collapsedByDefault = sidebar.dataset.collapsed === 'true';
    const setCollapsed = (collapsed) => {
        sidebar.dataset.collapsed = String(collapsed);
        collapse.setAttribute('aria-expanded', String(!collapsed));
        collapse.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    };

    try {
        const saved = localStorage.getItem(storageKey);
        if (saved !== null) setCollapsed(saved === 'true');
    } catch {
        setCollapsed(collapsedByDefault);
    }
    collapse.addEventListener('click', () => {
        const collapsed = sidebar.dataset.collapsed !== 'true';
        setCollapsed(collapsed);
        try {
            localStorage.setItem(storageKey, String(collapsed));
        } catch {
            // Keep the current layout when storage is unavailable.
        }
    });

    const desktop = window.matchMedia('(min-width: 768px)');
    const placeSidebar = () => {
        if (desktop.matches) {
            if (mobileDialog.open) mobileDialog.close();
            desktopHome.append(sidebar);
        } else {
            mobileDialog.querySelector('[data-mobile-sidebar]').append(sidebar);
        }
    };
    placeSidebar();
    desktop.addEventListener('change', placeSidebar);

    mobileOpen.addEventListener('click', () => {
        closePopovers();
        mobileDialog.showModal();
        sidebar.querySelector('[data-close-dialog]').focus();
    });
    for (const dialog of [mobileDialog, command]) {
        dialog.querySelector('[data-close-dialog]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', (event) => {
            if (event.target !== dialog) return;
            const bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom) {
                dialog.close();
            }
        });
    }

    const commandButton = document.querySelector('[data-open-command]');
    const input = document.getElementById('portal-command-filter');
    const groups = [...command.querySelectorAll('[data-command-group]')];
    const empty = command.querySelector('[data-command-empty]');

    function filterCommands() {
        const words = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
        for (const group of groups) {
            const heading = group.querySelector('h3').textContent.toLowerCase();
            for (const item of group.querySelectorAll('[data-command-result]')) {
                const label = `${heading} ${item.textContent.toLowerCase()}`;
                item.hidden = !words.every((word) => label.includes(word));
            }
            group.hidden = !group.querySelector('[data-command-result]:not([hidden])');
        }
        empty.hidden = groups.some((group) => !group.hidden);
    }

    const showCommands = () => {
        if (command.open) return;
        closePopovers();
        if (mobileDialog.open) mobileDialog.close();
        input.value = '';
        filterCommands();
        command.showModal();
        input.focus();
    };
    commandButton.addEventListener('click', showCommands);
    input.addEventListener('input', filterCommands);
    command.addEventListener('keydown', (event) => {
        const options = [...command.querySelectorAll('[data-command-result]:not([hidden])')];
        if (event.key === 'Enter' && event.target === input && options.length) {
            event.preventDefault();
            options[0].click();
        }
        if (!['ArrowUp', 'ArrowDown'].includes(event.key) || !options.length) return;
        event.preventDefault();
        const current = options.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? options[current + 1] : options[current - 1];
        (next || (event.key === 'ArrowUp' && current < 0 ? options.at(-1) : input)).focus();
    });
    document.addEventListener('keydown', (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            showCommands();
        }
    });
})();

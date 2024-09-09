// customize
const inkeepSettings = {
    isOpen: true,
    baseSettings: {
        apiKey: process.env.INKEEP_API_KEY,
        integrationId: process.env.INKEEP_INTEGRATION_ID,
        organizationId: process.env.INKEEP_ORGANIZATION_ID,
        primaryBrandColor: '#26D6FF', // your brand color, widget color scheme is derived from this
        organizationDisplayName: 'R2R',
        theme: {
          colorMode: {
            forcedColorMode: 'dark', // to sync dark mode with the widget
          },
        },
    },
    aiChatSettings: {
      // ...optional settings
      botAvatarSrcUrl:
        "https://www.sciphi.ai/screenshots/logo222_cut.png",
      quickQuestions: [
        "How do I get started?",
        "How does R2R implement hybrid search?",
        "How do I use the R2R API?",
        // "How do I use ",
        // "Example question 3?",
      ],
    },
    modalSettings: {
      isShortcutKeyEnabled: false, // disable default cmd+k behavior
      // ...optional settings
    },
  };

  // The Mintlify search triggers, which we'll reuse to trigger the Inkeep modal
  const searchButtonContainerIds = [
    "search-bar-entry",
    "search-bar-entry-mobile",
  ];

  // Clone and replace, needed to remove existing event listeners
  const clonedSearchButtonContainers = searchButtonContainerIds.map((id) => {
    const originalElement = document.getElementById(id);
    const clonedElement = originalElement.cloneNode(true);
    originalElement.parentNode.replaceChild(clonedElement, originalElement);

    return clonedElement;
  });

  // Load the Inkeep component library
  const inkeepScript = document.createElement("script");
  inkeepScript.type = "module";
  inkeepScript.src =
    "https://unpkg.com/@inkeep/widgets-embed@latest/dist/embed.js";
  document.body.appendChild(inkeepScript);

  // Once the Inkeep library is loaded, instantiate the UI components
  inkeepScript.addEventListener("load", function () {
    // Customization settings

    // for syncing with dark mode
    const colorModeSettings = {
      observedElement: document.documentElement,
      isDarkModeCallback: (el) => {
        return el.classList.contains("dark");
      },
      colorModeAttribute: "class",
    };

    // Instantiate the "Ask AI" pill chat button
    Inkeep().embed({
      componentType: "ChatButton",
      colorModeSync: colorModeSettings,
      properties: inkeepSettings,
    });

    // Instantiate the search bar modal
    const inkeepSearchModal = Inkeep({
      ...inkeepSettings.baseSettings,
    }).embed({
      componentType: "CustomTrigger",
      colorModeSync: colorModeSettings,
      properties: {
        ...inkeepSettings,
        isOpen: false,
        onClose: () => {
          inkeepSearchModal.render({
            isOpen: false,
          });
        },
      },
    });

    // When the Mintlify search bar elements are clicked, open the Inkeep search modal
    clonedSearchButtonContainers.forEach((trigger) => {
      trigger.addEventListener("click", function () {
        inkeepSearchModal.render({
          isOpen: true,
        });
      });
    });

    // Open the Inkeep Modal with cmd+k
    window.addEventListener(
      "keydown",
      (event) => {
        if (
          (event.metaKey || event.ctrlKey) &&
          (event.key === "k" || event.key === "K")
        ) {
          event.stopPropagation();
          inkeepSearchModal.render({ isOpen: true });
          return false;
        }
      },
      true
    );
  });

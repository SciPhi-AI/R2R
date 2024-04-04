import { useTheme } from "nextra-theme-docs";

const useInkeepSettings = () => {
  const { resolvedTheme } = useTheme();

  const baseSettings = {
    apiKey: process.env.INKEEP_API_KEY,
    integrationId:  process.env.INKEEP_INT_ID,
    organizationId: process.env.INKEEP_ORG_ID,
    primaryBrandColor: "#26D6FF", // your brand color, widget color scheme is derived from this
    organizationDisplayName: "R2R",
    // ...optional settings
    theme: {
      colorMode: {
        forcedColorMode: resolvedTheme, // to sync dark mode with the widget
      },
    },
  };

  const modalSettings = {
    // optional settings
  };

  const searchSettings = {
    // optional settings
  };

  const aiChatSettings = {
    // optional settings
    botAvatarSrcUrl: "/sciphi_logo.png", // use your own bot avatar
    quickQuestions: [
      "Which vector databases are supported?",
      "How do I customize my own RAG pipeline?",
      "How do I deploy an R2R pipeline to the cloud?",
    ],
  };

  return { baseSettings, aiChatSettings, searchSettings, modalSettings };
};

export default useInkeepSettings;

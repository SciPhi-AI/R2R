import { useEffect, useState } from "react";
import useInkeepSettings from "../useInkeepSettings";

export default function InkeepChatButton() {
  const [ChatButton, setChatButton] = useState(null);

  const { baseSettings, aiChatSettings, searchSettings, modalSettings } =
    useInkeepSettings();

  // load the library asynchronously
  useEffect(() => {
    const loadChatButton = async () => {
      try {
        const { InkeepChatButton } = await import("@inkeep/widgets");
        setChatButton(() => InkeepChatButton);
      } catch (error) {
        console.error("Failed to load ChatButton:", error);
      }
    };

    loadChatButton();
  }, []);

  const chatButtonProps = {
    baseSettings,
    aiChatSettings,
    searchSettings,
    modalSettings,
  };

  return ChatButton && <ChatButton {...chatButtonProps} />;
}

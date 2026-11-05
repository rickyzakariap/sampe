export const handleCardKeyDown = (event, activate) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  if (!event.repeat) activate();
};

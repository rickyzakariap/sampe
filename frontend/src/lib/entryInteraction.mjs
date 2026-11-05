export const confirmEntryDeletion = (confirm, label, onDelete) => {
  if (confirm(`${label}?`)) onDelete();
};

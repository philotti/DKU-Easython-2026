import { useEffect, useRef } from 'react';

export default function Drawer({ title, labelledBy, children, onClose, variant = '' }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const original = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => { dialog.close(); if (original?.isConnected) original.focus(); };
  }, []);
  return <dialog ref={ref} className={variant} aria-labelledby={labelledBy} onCancel={(event) => { event.preventDefault(); closeRef.current(); }} onClick={(event) => {
    if (event.target !== ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeRef.current();
  }}><div className="drawer-top"><span>{title}</span><button autoFocus onClick={onClose} aria-label="상세 닫기">×</button></div>{children}</dialog>;
}

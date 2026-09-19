export default function Avatar({ size = 36 }: { size?: number }) {
  return (
    <span
      className="flex items-center justify-center overflow-hidden rounded-full bg-white shadow-md"
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 24 24" className="h-full w-full" aria-hidden="true">
        <circle cx="12" cy="9.5" r="4.2" fill="#9ca3af" />
        <path d="M3.5 24c0-5.2 3.8-8.4 8.5-8.4s8.5 3.2 8.5 8.4z" fill="#9ca3af" />
      </svg>
    </span>
  );
}

// Знак SimpleCredits: пиксельное сердце с искрой на чёрном квадрате — тот же мотив, что и пиксельные иконки кабинета
export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="SimpleCredits">
      <rect width="64" height="64" rx="16" fill="#212124" />
      <path d="M17 18h10v5H17zM37 18h10v5H37zM12 23h40v15H12zM17 38h30v5H17zM22 43h20v5H22zM27 48h10v5H27zM50 7h3v3h3v3h-3v3h-3v-3h-3v-3h3z" fill="#c6f432" />
    </svg>
  );
}

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
  xmlns: 'http://www.w3.org/2000/svg',
  'aria-hidden': true,
}

export const RouteIcon = p => (
  <svg {...base} {...p}>
    <circle cx="6" cy="19" r="2.4" />
    <circle cx="18" cy="5" r="2.4" />
    <path d="M8.4 19h5.1a4 4 0 0 0 0-8h-3a4 4 0 0 1 0-8h1.1" />
  </svg>
)

export const ReportIcon = p => (
  <svg {...base} {...p}>
    <path d="M12 3.6 2.6 20h18.8L12 3.6Z" />
    <path d="M12 10v4" />
    <path d="M12 17.2h.01" />
  </svg>
)

export const SosIcon = p => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="M9.6 9.8a1.6 1.6 0 0 0-1.6 1.4c0 1.6 3.2 1.1 3.2 2.8a1.6 1.6 0 0 1-1.6 1.4" />
    <path d="M14.6 9.8h1.8v4.6h-1.8z" />
  </svg>
)

export const MeshIcon = p => (
  <svg {...base} {...p}>
    <circle cx="5" cy="6" r="2.2" />
    <circle cx="19" cy="9" r="2.2" />
    <circle cx="10" cy="18.5" r="2.2" />
    <path d="M7 6.8 16.9 8.6M17.9 11 11.5 16.6M8.3 16.9 6 8.2" />
  </svg>
)

export const SettingsIcon = p => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.2a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.5 15H3.3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 8.3l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9.3a1.6 1.6 0 0 0 1-1.5V3.9a2 2 0 1 1 4 0V4a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v.1a1.6 1.6 0 0 0 1.5 1h.2a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z" />
  </svg>
)

export const WifiOff = p => (
  <svg {...base} {...p}>
    <path d="m2 2 20 20" />
    <path d="M8.6 15.4a5 5 0 0 1 6.8 0" />
    <path d="M5 12.1a10 10 0 0 1 3.4-2.3M19 12.1a10 10 0 0 0-6.6-2.7" />
    <path d="M1.6 8.6a15 15 0 0 1 4.6-2.9M22.4 8.6a15 15 0 0 0-9.9-3.4" />
    <path d="M12 19.5h.01" />
  </svg>
)

export const Wifi = p => (
  <svg {...base} {...p}>
    <path d="M8.6 15.4a5 5 0 0 1 6.8 0" />
    <path d="M5 12.1a10 10 0 0 1 14 0" />
    <path d="M1.6 8.6a15 15 0 0 1 20.8 0" />
    <path d="M12 19.5h.01" />
  </svg>
)

export const Camera = p => (
  <svg {...base} {...p}>
    <path d="M3 8.6h3.2L8 6h8l1.8 2.6H21v10.8H3Z" />
    <circle cx="12" cy="13.4" r="3.4" />
  </svg>
)

export const Pin = p => (
  <svg {...base} {...p}>
    <path d="M12 21.5s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
    <circle cx="12" cy="10.3" r="2.6" />
  </svg>
)

export const Check = p => (
  <svg {...base} {...p}>
    <path d="m4.5 12.5 5 5 10-11" />
  </svg>
)

export const Clock = p => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="8.6" />
    <path d="M12 7.2v5.1l3.2 1.9" />
  </svg>
)

export const Upload = p => (
  <svg {...base} {...p}>
    <path d="M12 16.5V4.4" />
    <path d="m7.4 9 4.6-4.6L16.6 9" />
    <path d="M4.5 15.5v3.2a1.4 1.4 0 0 0 1.4 1.4h12.2a1.4 1.4 0 0 0 1.4-1.4v-3.2" />
  </svg>
)

export const Refresh = p => (
  <svg {...base} {...p}>
    <path d="M20.4 12a8.4 8.4 0 1 1-2.5-6" />
    <path d="M19.6 3.4V9h-5.5" />
  </svg>
)

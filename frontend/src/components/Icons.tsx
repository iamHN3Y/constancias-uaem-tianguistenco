/**
 * Iconos SVG inline, portados 1:1 de los paths usados en las plantillas
 * Jinja2 originales. Componentes livianos: solo <svg><path/></svg>.
 */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export const IconInvitado = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 12a5 5 0 100-10 5 5 0 000 10zm0 2c-4.4 0-8 2.2-8 5v1a1 1 0 001 1h14a1 1 0 001-1v-1c0-2.8-3.6-5-8-5z" />
  </Svg>
);

export const IconAdmin = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 1L3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5l-9-4zm0 10.5h7c-.5 4.1-3.3 7.8-7 9V11.5H5V6.3l7-3.1v8.3z" />
  </Svg>
);

export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 2a8 8 0 105.3 14l5.4 5.4 1.4-1.4-5.4-5.4A8 8 0 0010 2zm0 2a6 6 0 110 12 6 6 0 010-12z" />
  </Svg>
);

export const IconFile = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 4a2 2 0 012-2h8l6 6v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm9 1v5h5l-5-5z" />
  </Svg>
);

export const IconCalendar = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 2a1 1 0 011 1v1h8V3a1 1 0 112 0v1h1a2 2 0 012 2v13a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h1V3a1 1 0 011-1zm12 7H5v10h14V9z" />
  </Svg>
);

export const IconCareer = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3L1 9l11 6 9-4.9V17h2V9L12 3zm-7 9.6V17c0 1.7 3.1 3 7 3s7-1.3 7-3v-4.4l-7 3.8-7-3.8z" />
  </Svg>
);

export const IconWarning = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
  </Svg>
);

export const IconInfo = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
  </Svg>
);

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z" />
  </Svg>
);

export const IconBack = (p: IconProps) => (
  <Svg {...p}>
    <path d="M15.4 7.4L14 6l-6 6 6 6 1.4-1.4-4.6-4.6 4.6-4.6z" />
  </Svg>
);

export const IconClose = (p: IconProps) => (
  <Svg {...p}>
    <path d="M18.3 5.7L12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7 4.3 4.3l6.3 6.3 6.3-6.3z" />
  </Svg>
);

export const IconDownload = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 20h14v-2H5v2zM12 2v12.2l4-4 1.4 1.4L12 17 6.6 11.6 8 10.2l4 4V2h0z" />
  </Svg>
);

export const IconTrash = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 7h12l-1 13a2 2 0 01-2 2H9a2 2 0 01-2-2L6 7zm3-3h6l1 2h4v2H4V6h4l1-2z" />
  </Svg>
);

export const IconUpload = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 2l5 5h-3v6h-4V7H7l5-5zM5 18h14v2H5v-2z" />
  </Svg>
);

export const IconPlus = (p: IconProps) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" {...p}>
    <path d="M12 5v14m-7-7h14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
  </svg>
);

export const IconEye = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5c-5 0-9 4.5-10 7 1 2.5 5 7 10 7s9-4.5 10-7c-1-2.5-5-7-10-7zm0 11a4 4 0 110-8 4 4 0 010 8zm0-6a2 2 0 100 4 2 2 0 000-4z" />
  </Svg>
);

export const IconFields = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5zm4 3h10v2H7V8zm0 4h10v2H7v-2zm0 4h6v2H7v-2z" />
  </Svg>
);

export const IconSun = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 7a5 5 0 100 10 5 5 0 000-10zm0-5a1 1 0 011 1v2a1 1 0 11-2 0V3a1 1 0 011-1zm0 16a1 1 0 011 1v2a1 1 0 11-2 0v-2a1 1 0 011-1zM4.2 5.6a1 1 0 011.4 0l1.5 1.4A1 1 0 015.7 8.4L4.2 7a1 1 0 010-1.4zm12.7 12.7a1 1 0 011.4 0l1.5 1.4a1 1 0 01-1.4 1.4l-1.5-1.4a1 1 0 010-1.4zM2 12a1 1 0 011-1h2a1 1 0 110 2H3a1 1 0 01-1-1zm17 0a1 1 0 011-1h2a1 1 0 110 2h-2a1 1 0 01-1-1zM5.6 19.8l1.4-1.5a1 1 0 011.4 1.4l-1.4 1.5a1 1 0 01-1.4-1.4zM18.3 7.1l1.4-1.5a1 1 0 011.4 1.4l-1.4 1.5a1 1 0 01-1.4-1.4z" />
  </Svg>
);

export const IconMoon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 109.8 9.8z" />
  </Svg>
);

export const IconHelp = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 16.5a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5zm1.8-6.3c-.7.5-.9.8-.9 1.4v.4h-1.8v-.5c0-1.2.5-1.9 1.4-2.5.7-.5 1-.8 1-1.4 0-.7-.5-1.1-1.3-1.1-.8 0-1.3.4-1.7 1.1l-1.5-.9C9 7.9 10.1 7.2 11.6 7.2c1.9 0 3.2 1 3.2 2.7 0 1.1-.5 1.7-1.6 2.3z" />
  </Svg>
);

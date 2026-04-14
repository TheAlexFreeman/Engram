export type NavbarSvgLogoProps = React.SVGProps<SVGSVGElement>;

export default function NavbarSvgLogo(props: NavbarSvgLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="26"
      height="20"
      fill="none"
      viewBox="0 0 26 20"
      {...props}
    >
      <g fill="#4E49D1">
        <path d="M22.544 19.997H.781a.576.576 0 01-.498-.863L11.163.288a.576.576 0 01.998 0l1.98 3.432a.576.576 0 010 .576L8.139 14.693a.576.576 0 00.499.863h12.005c.206 0 .396.109.499.288l1.9 3.291a.576.576 0 01-.498.865v-.003z"></path>
        <path d="M25.286 15.554H21.27a.51.51 0 01-.44-.254L14.454 4.26a.506.506 0 010-.508L16.463.274a.509.509 0 01.881 0l8.383 14.519a.509.509 0 01-.44.763v-.002z"></path>
      </g>
    </svg>
  );
}

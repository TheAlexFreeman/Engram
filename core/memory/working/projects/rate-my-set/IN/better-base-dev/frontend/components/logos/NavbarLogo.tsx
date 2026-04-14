import NavbarSvgLogo, { type NavbarSvgLogoProps } from './NavbarSvgLogo';

export type NavbarLogoProps = NavbarSvgLogoProps;

export default function NavbarLogo(props: NavbarLogoProps) {
  return <NavbarSvgLogo {...props} />;
}

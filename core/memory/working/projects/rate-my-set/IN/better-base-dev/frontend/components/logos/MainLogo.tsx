import MainSvgLogo, { type MainSvgLogoProps } from './MainSvgLogo';

export type MainLogoProps = MainSvgLogoProps;

export default function MainLogo(props: MainLogoProps) {
  return <MainSvgLogo {...props} />;
}

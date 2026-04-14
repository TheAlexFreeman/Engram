export type MainSvgLogoProps = React.SVGProps<SVGSVGElement>;

export default function MainSvgLogo(props: MainSvgLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="41"
      height="32"
      fill="none"
      viewBox="0 0 41 32"
      {...props}
    >
      <g fill="#4E49D1">
        <path d="M35.742 31.995H.922a.92.92 0 01-.798-1.38L17.534.46a.922.922 0 011.595 0l3.169 5.49a.922.922 0 010 .923l-9.603 16.634a.921.921 0 00.798 1.381H32.7c.33 0 .633.175.798.461l3.041 5.267A.922.922 0 0135.744 32v-.005z"></path>
        <path d="M40.13 24.887h-6.428a.815.815 0 01-.704-.406L22.8 6.816a.81.81 0 010-.812L26.013.439a.814.814 0 011.41 0l13.412 23.23a.814.814 0 01-.705 1.22v-.002z"></path>
      </g>
    </svg>
  );
}

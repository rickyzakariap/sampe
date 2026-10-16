const LOGO = "/branding/sampe-dark-landscape.png";
const MARK = "/branding/sampe-dark-portrait.png";

// The original PNGs have transparent margins. These viewports only hide that
// empty space; the logo artwork keeps its original shape, colors, and ratio.
export const BrandMark = () => (
  <span role="img" aria-label="Logo SAMPE" className="relative block h-9 w-9 shrink-0 overflow-hidden">
    <img src={MARK} alt="" className="pointer-events-none absolute left-[-79px] top-[-62px] w-[198px] max-w-none" />
  </span>
);

export const BrandWordmark = ({ compact = false }) => (
  <span role="img" aria-label="SAMPE — System Analytic Marketplace" className={`relative block shrink-0 overflow-hidden ${compact ? "h-[77px] w-[160px]" : "h-[96px] w-[200px]"}`}>
    <img src={LOGO} alt="" className={`pointer-events-none absolute max-w-none ${compact ? "left-[-33px] top-[-75px] w-[227px]" : "left-[-41px] top-[-94px] w-[284px]"}`} />
  </span>
);

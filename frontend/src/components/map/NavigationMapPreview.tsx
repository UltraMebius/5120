function NavigationMapPreview() {
  return (
    <div
      aria-label="Phase 1 map preview showing the selected walking route, current position and destination"
      className="map-preview"
      role="img"
    >
      <svg
        aria-hidden="true"
        className="map-preview__streets"
        preserveAspectRatio="none"
        viewBox="0 0 1000 720"
      >
        <path d="M-30 115 C220 80 390 165 1030 60" />
        <path d="M-20 370 C250 315 530 400 1030 310" />
        <path d="M-20 625 C300 535 690 670 1030 555" />
        <path d="M135 -20 C185 170 110 430 250 760" />
        <path d="M420 -20 C350 200 520 420 435 760" />
        <path d="M720 -20 C640 235 815 465 755 760" />
        <path d="M930 -20 C850 210 1000 450 915 760" />
      </svg>
      <svg
        aria-hidden="true"
        className="map-preview__route"
        preserveAspectRatio="none"
        viewBox="0 0 1000 720"
      >
        <path d="M210 590 C270 505 280 420 405 390 S610 405 645 300 S730 170 825 115" />
      </svg>
      <span className="map-marker map-marker--current" aria-hidden="true">
        <span />
      </span>
      <span className="map-marker map-marker--destination" aria-hidden="true">
        <span>●</span>
      </span>
      <span className="map-preview__label">Phase 1 map preview</span>
      <span className="map-preview__attribution">Mapbox integration boundary</span>
    </div>
  );
}

export default NavigationMapPreview;

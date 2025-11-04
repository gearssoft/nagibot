// #############################
// ## filename : simulator/robot.js
// ## 설명 : 로봇 시뮬레이터 (바이시클+액추에이터) + 지도좌표 자동 갱신
// ## 작성자 : gbox3d 
// ## 위 주석은 수정하지 마세요.
// #############################

export class Robot {
  /**
   * @param {{
   *   id?:number, x?:number, y?:number, angle?:number,
   *   mode?:string, mission?:string,
   *   // vehicle params
   *   wheelbase?:number, wheelRadius?:number, steerLimitDeg?:number, maxWheelRPM?:number,
   *   // actuators
   *   WheelSpeed?:number, WheelAngle?:number, WheelOmega?:number,
   *   // geo reference (지도 기준점)
   *   originLon?:number, originLat?:number,
   *   metersPerDeg?:number
   * }} opts
   */
  constructor(opts = {}) {
    // ---- pose / mode ----
    this.id = Number(opts.id ?? 1);
    this.x = Number(opts.x ?? 0);
    this.y = Number(opts.y ?? 0);
    this.headingDeg = Number(opts.angle ?? 0);
    this.mode = String(opts.mode ?? "manual");
    this.mission = String(opts.mission ?? "stop");

    // ---- vehicle params ----
    this.wheelbase     = Number(opts.wheelbase ?? 1.2);
    this.wheelRadius   = Number(opts.wheelRadius ?? 0.15);
    this.steerLimitDeg = Number(opts.steerLimitDeg ?? 35);
    this.maxWheelRPM   = Number(opts.maxWheelRPM ?? 300);

    // ---- actuators ----
    this.WheelSpeed       = Number(opts.WheelSpeed ?? 0);     // [RPM]
    this.WheelAngleCmdDeg = Number(opts.WheelAngle ?? 0);     // [deg]
    this.WheelOmega       = Number(opts.WheelOmega ?? 2.0);   // [rad/s]
    this.steerDeg = this._clampDeg(this.WheelAngleCmdDeg);
    this.v = 0;
    this.drag = 0.98;

    this.WheelSpeed = this._clamp(this.WheelSpeed, -this.maxWheelRPM, this.maxWheelRPM);
    this.WheelAngleCmdDeg = this._clampDeg(this.WheelAngleCmdDeg);

    // ---- geo reference & current lon/lat ----
    this.originLon = Number(opts.originLon ?? 127.0);
    this.originLat = Number(opts.originLat ?? 37.5);
    this.metersPerDeg = Number(opts.metersPerDeg ?? 111320); // 위도 1도 ≈ 111.32km
    this.longitude = Number.isFinite(opts.longitude) ? Number(opts.longitude) : null;
    this.latitude  = Number.isFinite(opts.latitude)  ? Number(opts.latitude)  : null;

    // 초기 lon/lat이 없으면 x,y로부터 계산
    if (this.longitude == null || this.latitude == null) {
      const { lon, lat } = this._xyToLonLat(this.x, this.y);
      this.longitude = lon;
      this.latitude = lat;
    }
  }

  static fromMetadata(m = {}) {
    const r = m.robot ?? m;
    const g = m.geo ?? {};
    return new Robot({
      id: r?.id, x: r?.x, y: r?.y, angle: r?.angle,
      mode: r?.mode, mission: r?.mission,
      wheelbase: r?.wheelbase, wheelRadius: r?.wheelRadius,
      steerLimitDeg: r?.steerLimitDeg, maxWheelRPM: r?.maxWheelRPM,
      WheelSpeed: r?.WheelSpeed, WheelAngle: r?.WheelAngle, WheelOmega: r?.WheelOmega,
      originLon: g?.originLon ?? r?.originLon,    // 둘 중 하나라도 있으면 사용
      originLat: g?.originLat ?? r?.originLat,
      metersPerDeg: g?.metersPerDeg ?? r?.metersPerDeg,
      longitude: r?.longitude, latitude: r?.latitude,
    });
  }

  // ===== 외부 API =====
  setActuators({ WheelSpeed, WheelAngle, WheelOmega } = {}) {
    if (WheelSpeed !== undefined) this.WheelSpeed = this._clamp(Number(WheelSpeed), -this.maxWheelRPM, this.maxWheelRPM);
    if (WheelAngle !== undefined) this.WheelAngleCmdDeg = this._clampDeg(Number(WheelAngle));
    if (WheelOmega !== undefined) this.WheelOmega = Math.max(0, Number(WheelOmega));
  }

  setGeoOrigin(originLon, originLat, metersPerDeg) {
    if (originLon != null) this.originLon = Number(originLon);
    if (originLat != null) this.originLat = Number(originLat);
    if (metersPerDeg != null) this.metersPerDeg = Number(metersPerDeg);
    // 기준점이 바뀌면 현 x,y로부터 lon/lat 재계산
    const p = this._xyToLonLat(this.x, this.y);
    this.longitude = p.lon;
    this.latitude = p.lat;
  }

  /** 메타/상태 패치 */
  applyPatch(p = {}) {
    if ("x" in p) this.x = Number(p.x);
    if ("y" in p) this.y = Number(p.y);
    if ("angle" in p) this.headingDeg = Number(p.angle);
    if ("mode" in p) this.mode = String(p.mode);
    if ("mission" in p) this.mission = String(p.mission);

    if ("wheelbase" in p) this.wheelbase = Number(p.wheelbase);
    if ("wheelRadius" in p) this.wheelRadius = Number(p.wheelRadius);
    if ("steerLimitDeg" in p) this.steerLimitDeg = Number(p.steerLimitDeg);
    if ("maxWheelRPM" in p) this.maxWheelRPM = Number(p.maxWheelRPM);

    if ("WheelSpeed" in p || "WheelAngle" in p || "WheelOmega" in p) {
      this.setActuators({
        WheelSpeed: p.WheelSpeed,
        WheelAngle: p.WheelAngle,
        WheelOmega: p.WheelOmega,
      });
    }

    if ("originLon" in p || "originLat" in p || "metersPerDeg" in p) {
      this.setGeoOrigin(p.originLon, p.originLat, p.metersPerDeg);
    }
    if ("longitude" in p && "latitude" in p) {
      // 외부에서 절대 위경도 지정 → 로컬(x,y) 역변환
      const xy = this._lonLatToXY(Number(p.longitude), Number(p.latitude));
      this.x = xy.x;
      this.y = xy.y;
      this.longitude = Number(p.longitude);
      this.latitude = Number(p.latitude);
    }
  }

  // ===== 시뮬레이션 1 step =====
  update(dt) {
    if (dt <= 0) return;

    // wheel RPM -> v[m/s]
    const omegaWheel = (2 * Math.PI) * (this.WheelSpeed / 60.0);
    this.v = omegaWheel * this.wheelRadius;

    // steering slew
    const maxSteerRateDeg = this.WheelOmega * (180 / Math.PI);
    const err = this._wrapDeg(this.WheelAngleCmdDeg - this.steerDeg);
    const maxStep = maxSteerRateDeg * dt;
    const step = Math.max(-maxStep, Math.min(maxStep, err));
    this.steerDeg = this._clampDeg(this.steerDeg + step);

    // bicycle model
    const theta = this.headingDeg * Math.PI / 180;
    const delta = this.steerDeg * Math.PI / 180;
    const thetaDot = (this.wheelbase > 0) ? (this.v / this.wheelbase) * Math.tan(delta) : 0;
    const xDot = this.v * Math.cos(theta);
    const yDot = this.v * Math.sin(theta);

    this.x += xDot * dt;
    this.y += yDot * dt;
    this.headingDeg = this._normalizeDeg(this.headingDeg + (thetaDot * 180 / Math.PI) * dt);
    this.v *= this.drag;

    // 지도 좌표 자동 갱신
    const { lon, lat } = this._xyToLonLat(this.x, this.y);
    this.longitude = lon;
    this.latitude = lat;
  }

  toJSON() {
    return {
      id: this.id,
      x: this.x, y: this.y,
      angle: this.headingDeg,
      mode: this.mode, mission: this.mission,

      wheelbase: this.wheelbase, wheelRadius: this.wheelRadius,
      steerLimitDeg: this.steerLimitDeg, maxWheelRPM: this.maxWheelRPM,

      WheelSpeed: this.WheelSpeed,
      WheelAngle: this.WheelAngleCmdDeg,
      WheelOmega: this.WheelOmega,
      steerDeg: this.steerDeg,
      v: this.v,

      longitude: this.longitude,
      latitude: this.latitude,

      // 참고로 geo 기준점도 함께 노출(클라가 변환 필요 시 사용)
      originLon: this.originLon,
      originLat: this.originLat,
      metersPerDeg: this.metersPerDeg
    };
  }

  // ===== 좌표 변환 유틸 =====
  _xyToLonLat(x, y) {
    // 단순 평면 근사 (작은 영역 가정)
    const lat = this.originLat + (y / this.metersPerDeg);
    const lon = this.originLon + (x / (this.metersPerDeg * Math.cos(this.originLat * Math.PI / 180)));
    return { lon, lat };
  }
  _lonLatToXY(lon, lat) {
    const y = (lat - this.originLat) * this.metersPerDeg;
    const x = (lon - this.originLon) * this.metersPerDeg * Math.cos(this.originLat * Math.PI / 180);
    return { x, y };
  }

  // ===== utils =====
  _clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  _normalizeDeg(d) { let a = d % 360; if (a < 0) a += 360; return a; }
  _wrapDeg(d) { let a = ((d + 180) % 360); if (a < 0) a += 360; return a - 180; }
  _clampDeg(d) { return this._clamp(d, -this.steerLimitDeg, this.steerLimitDeg); }
}

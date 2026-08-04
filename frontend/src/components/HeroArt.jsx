// 메인 히어로 일러스트 (2026-08-04)
//  예전엔 그라데이션 상자에 🤝 이모지 120px 을 얹어 뒀다. 이모지는 OS·브라우저마다
//  모양이 달라(윈도우·안드로이드·iOS 가 전부 다른 그림) 발표 화면에서 무엇이 나올지
//  보장되지 않는다. 벡터로 직접 그려 어디서 열어도 같게 보이게 했다.
//
//  구성 — 이름 그대로 '이음(잇는 것)'
//    · 위의 호(arc)   = 흩어진 제도를 잇는 다리. 그 위 세 점이 덜다·잇다·나누다.
//    · 아래 두 사람   = 돌보는 청년과 가족. 어깨를 겹쳐 그려 '혼자가 아님'을 나타냈다.
//  색은 전부 tokens.css 의 teal·sand 램프에서 가져왔다(새 색을 만들지 않았다).
export default function HeroArt() {
  return (
    <svg viewBox="0 0 360 280" width="100%" height="100%"
      preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="heroArtTitle">
      <title id="heroArtTitle">
        덜다·잇다·나누다 세 갈래를 잇는 다리와, 어깨를 맞댄 청년과 가족
      </title>

      {/* 바닥 그림자 — 인물이 공중에 뜨지 않게 */}
      <ellipse cx="180" cy="252" rx="118" ry="13" fill="#f5ecdd" />

      {/* 잇는 호 — 넓고 옅은 층을 깔고 그 위에 실선을 얹어 부드럽게 */}
      <path d="M 50 165 Q 180 45 310 165" fill="none" stroke="#d3f1ec"
        strokeWidth="12" strokeLinecap="round" />
      <path d="M 50 165 Q 180 45 310 165" fill="none" stroke="#6fcfc2"
        strokeWidth="2.5" strokeLinecap="round" />

      {/* ── 인물 ── 뒤(가족) 먼저 그려 앞사람이 겹치게 한다 */}
      <g>
        <path d="M 172 250 Q 172 219 199 219 Q 226 219 226 250 Z" fill="#a7e3da" />
        <circle cx="199" cy="201" r="15" fill="#6fcfc2" />
      </g>
      <g>
        <path d="M 120 250 Q 120 212 148 212 Q 176 212 176 250 Z" fill="#1f9c8d" />
        <circle cx="148" cy="193" r="18" fill="#157f73" />
      </g>

      {/* ── 호 위의 세 점 — 왼쪽부터 덜다·잇다·나누다 ── */}

      {/* 덜다 · 물방울 */}
      <g transform="translate(102 127)">
        <circle r="17" fill="#ffffff" stroke="#1f9c8d" strokeWidth="2.5" />
        <path d="M 0 -9 C 4.5 -3 7 1 7 3.5 A 7 7 0 1 1 -7 3.5 C -7 1 -4.5 -3 0 -9 Z"
          fill="#3fb6a7" />
      </g>

      {/* 잇다 · 새싹 */}
      <g transform="translate(180 105)">
        <circle r="17" fill="#ffffff" stroke="#1f9c8d" strokeWidth="2.5" />
        <path d="M 0 8 L 0 -1" stroke="#157f73" strokeWidth="2" strokeLinecap="round" />
        <path d="M 0 1 C 1 -5 5 -8 9 -8 C 9 -3 5 1 0 1 Z" fill="#1f9c8d" />
        <path d="M 0 5 C -1 1 -4 -1 -7 -1 C -7 3 -4 6 0 5 Z" fill="#6fcfc2" />
      </g>

      {/* 나누다 · 마음 */}
      <g transform="translate(258 127)">
        <circle r="17" fill="#ffffff" stroke="#1f9c8d" strokeWidth="2.5" />
        <path d="M 0 7 C -9 0.5 -7.5 -6 -3.5 -6 C -1.5 -6 0 -4.2 0 -2.5
                 C 0 -4.2 1.5 -6 3.5 -6 C 7.5 -6 9 0.5 0 7 Z" fill="#3fb6a7" />
      </g>

      {/* 여백의 작은 점 — 화면이 비어 보이지 않게. 의미는 없다 */}
      <circle cx="62" cy="92" r="4" fill="#a7e3da" />
      <circle cx="300" cy="76" r="5.5" fill="#d3f1ec" />
      <circle cx="322" cy="196" r="4" fill="#f5ecdd" />
      <circle cx="44" cy="206" r="5" fill="#d3f1ec" />
    </svg>
  )
}

import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { PageHead } from '../../components/ui/index.jsx'
//  ★ 2026-08-06 — 백엔드 주소는 client.js 하나에서 가져온다.
//    (예전엔 이 화면이 VITE_API_BASE_URL 로 8000 을 직접 때렸다 — 이름도 기본값도
//     client.js 와 달라서, 배포하면 여기만 조용히 죽는 구조였다)
import { API_BASE } from '../../api/client.js'

async function getDrivingRoute({
  originLatitude,
  originLongitude,
  destinationLatitude,
  destinationLongitude,
}) {
  const params = new URLSearchParams({
    origin_latitude: String(originLatitude),
    origin_longitude: String(originLongitude),
    destination_latitude: String(destinationLatitude),
    destination_longitude: String(destinationLongitude),
  })

  const response = await fetch(
    `${API_BASE}/support-facilities/route?${params}`,
  )
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(
      data?.detail ?? '도로 경로를 불러오지 못했습니다.',
    )
  }

  return data
}

const DEFAULT_KEYWORD = '복지시설'
const DEFAULT_POSITION = {
  latitude: 37.5665,
  longitude: 126.978,
}

const CURRENT_LOCATION_MARKER_SVG = `
  <svg xmlns="http://www.w3.org/2000/svg" width="36" height="42" viewBox="0 0 36 42">
    <defs>
      <filter id="shadow" x="-40%" y="-30%" width="180%" height="190%">
        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.28"/>
      </filter>
    </defs>
    <path
      d="M18 2C9.72 2 3 8.72 3 17c0 10.72 15 23 15 23s15-12.28 15-23C33 8.72 26.28 2 18 2z"
      fill="#E53935"
      stroke="#FFFFFF"
      stroke-width="3"
      filter="url(#shadow)"
    />
    <circle cx="18" cy="17" r="6" fill="#FFFFFF"/>
    <circle cx="18" cy="17" r="3" fill="#E53935"/>
  </svg>
`

const CURRENT_LOCATION_MARKER_URL =
  `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
    CURRENT_LOCATION_MARKER_SVG,
  )}`

function formatRouteDistance(distance) {
  const meters = Number(distance)
  if (!Number.isFinite(meters)) return '거리 정보 없음'
  if (meters < 1000) return `${meters}m`
  return `${(meters / 1000).toFixed(1)}km`
}

function formatRouteDuration(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value)) return '시간 정보 없음'
  return `약 ${Math.max(1, Math.ceil(value / 60))}분`
}

function loadKakaoMapSdk(appKey) {
  return new Promise((resolve, reject) => {
    const finishLoading = () => {
      window.kakao.maps.load(() => {
        if (!window.kakao?.maps?.services) {
          reject(
            new Error(
              '카카오 지도 장소검색 서비스를 불러오지 못했습니다.',
            ),
          )
          return
        }

        resolve()
      })
    }

    if (window.kakao?.maps?.services) {
      finishLoading()
      return
    }

    const existingScript = document.getElementById('kakao-map-sdk')

    if (existingScript) {
      existingScript.remove()
    }

    const script = document.createElement('script')
    script.id = 'kakao-map-sdk'
    script.async = true
    script.src =
      'https://dapi.kakao.com/v2/maps/sdk.js' +
      `?appkey=${appKey}&autoload=false&libraries=services`

    script.onload = () => {
      if (!window.kakao?.maps) {
        reject(new Error('카카오 지도 SDK를 불러오지 못했습니다.'))
        return
      }

      finishLoading()
    }

    script.onerror = () => {
      script.remove()
      reject(new Error('카카오 지도 SDK 요청에 실패했습니다.'))
    }

    document.head.appendChild(script)
  })
}

export default function ResourceMap() {
  const location = useLocation()
  const recommendation = location.state?.recommendation ?? null
  const initialKeyword =
    recommendation?.map_place_name ||
    recommendation?.facility_name ||
    DEFAULT_KEYWORD

  const mapElementRef = useRef(null)
  const mapRef = useRef(null)
  const placesRef = useRef(null)
  const markersRef = useRef([])
  const currentMarkerRef = useRef(null)
  const currentInfoWindowRef = useRef(null)
  const recommendedMarkerRef = useRef(null)
  const recommendedInfoWindowRef = useRef(null)
  const routePolylineRef = useRef(null)
  const infoWindowRef = useRef(null)
  const searchPositionRef = useRef(null)

  const [keyword, setKeyword] = useState(initialKeyword)
  const [mapReady, setMapReady] = useState(false)
  const [searching, setSearching] = useState(false)
  const [resultCount, setResultCount] = useState(null)
  const [mapError, setMapError] = useState('')
  const [locationNotice, setLocationNotice] = useState('')
  const [routeLoading, setRouteLoading] = useState(false)
  const [routeInfo, setRouteInfo] = useState(null)
  const [routeError, setRouteError] = useState('')

  const clearPlaceMarkers = () => {
    markersRef.current.forEach((marker) => marker.setMap(null))
    markersRef.current = []
    infoWindowRef.current?.close()
  }

  const searchPlaces = (searchKeyword, position) => {
    const trimmedKeyword = searchKeyword.trim() || DEFAULT_KEYWORD
    const map = mapRef.current
    const places = placesRef.current
    const searchPosition = position || searchPositionRef.current

    if (!map || !places || !searchPosition) {
      return
    }

    setSearching(true)
    setMapError('')

    places.keywordSearch(
      trimmedKeyword,
      (placesResult, status) => {
        setSearching(false)
        clearPlaceMarkers()

        if (status === window.kakao.maps.services.Status.ZERO_RESULT) {
          setResultCount(0)
          return
        }

        if (status !== window.kakao.maps.services.Status.OK) {
          setResultCount(null)
          setMapError('장소 검색 중 오류가 발생했습니다.')
          return
        }

        setResultCount(placesResult.length)

        const bounds = new window.kakao.maps.LatLngBounds()
        bounds.extend(searchPosition)

        placesResult.forEach((place) => {
          const positionForPlace = new window.kakao.maps.LatLng(
            Number(place.y),
            Number(place.x),
          )

          const marker = new window.kakao.maps.Marker({
            map,
            position: positionForPlace,
          })

          window.kakao.maps.event.addListener(marker, 'click', () => {
            const kakaoDetailUrl = place.id
              ? `https://place.map.kakao.com/m/${encodeURIComponent(place.id)}`
              : place.place_url

            const content = document.createElement('div')
            content.style.padding = '9px 12px'
            content.style.fontSize = '13px'
            content.style.lineHeight = '1.5'
            content.style.minWidth = '170px'

            const name = document.createElement('strong')
            name.textContent = place.place_name
            content.appendChild(name)

            const address = document.createElement('div')
            address.style.color = '#667085'
            address.textContent =
              place.road_address_name ||
              place.address_name ||
              '주소 정보 없음'
            content.appendChild(address)

            if (place.category_name) {
              const category = document.createElement('div')
              category.style.color = '#667085'
              category.textContent = `분류: ${place.category_name}`
              content.appendChild(category)
            }

            const phone = document.createElement('div')
            phone.style.marginTop = '3px'
            phone.textContent = place.phone
              ? `전화: ${place.phone}`
              : '전화번호 정보 없음'
            content.appendChild(phone)

            if (kakaoDetailUrl) {
              const detailLink = document.createElement('a')
              detailLink.href = kakaoDetailUrl
              detailLink.target = '_blank'
              detailLink.rel = 'noreferrer'
              detailLink.textContent = '카카오맵 상세정보 ↗'
              detailLink.style.display = 'inline-block'
              detailLink.style.marginTop = '6px'
              detailLink.style.color = '#00897b'
              detailLink.style.fontWeight = '700'
              content.appendChild(detailLink)
            }

            infoWindowRef.current.setContent(content)
            infoWindowRef.current.open(map, marker)

            if (kakaoDetailUrl) {
              window.open(
                kakaoDetailUrl,
                '_blank',
                'noopener,noreferrer',
              )
            }
          })

          markersRef.current.push(marker)
          bounds.extend(positionForPlace)
        })

        map.setBounds(bounds)
      },
      {
        location: searchPosition,
        radius: 5000,
        sort: window.kakao.maps.services.SortBy.DISTANCE,
      },
    )
  }

  useEffect(() => {
    const appKey = import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY

    if (!appKey) {
      setMapError('.env에 VITE_KAKAO_JAVASCRIPT_KEY를 설정해 주세요.')
      return undefined
    }

    let cancelled = false

    loadKakaoMapSdk(appKey)
      .then(() => {
        if (cancelled || !mapElementRef.current) {
          return
        }

        const defaultPosition = new window.kakao.maps.LatLng(
          DEFAULT_POSITION.latitude,
          DEFAULT_POSITION.longitude,
        )

        const map = new window.kakao.maps.Map(mapElementRef.current, {
          center: defaultPosition,
          level: 5,
        })

        mapRef.current = map
        placesRef.current = new window.kakao.maps.services.Places()
        infoWindowRef.current = new window.kakao.maps.InfoWindow()
        searchPositionRef.current = defaultPosition
        setMapReady(true)

        const drawRecommendedRoute = async (
          originLatitude,
          originLongitude,
        ) => {
          if (!recommendation) return

          const destinationLatitude = Number(
            recommendation.map_latitude,
          )
          const destinationLongitude = Number(
            recommendation.map_longitude,
          )

          if (
            !Number.isFinite(destinationLatitude) ||
            !Number.isFinite(destinationLongitude)
          ) {
            setRouteError('추천 기관의 지도 좌표가 없습니다.')
            return
          }

          const destinationPosition =
            new window.kakao.maps.LatLng(
              destinationLatitude,
              destinationLongitude,
            )

          recommendedMarkerRef.current?.setMap(null)
          recommendedMarkerRef.current =
            new window.kakao.maps.Marker({
              map,
              position: destinationPosition,
            })

          const recommendedLabel = document.createElement('div')
          recommendedLabel.textContent =
            recommendation.map_place_name ||
            recommendation.facility_name ||
            '추천 기관'
          recommendedLabel.style.padding = '7px 10px'
          recommendedLabel.style.fontSize = '13px'
          recommendedLabel.style.fontWeight = '700'
          recommendedLabel.style.whiteSpace = 'nowrap'

          recommendedInfoWindowRef.current?.close()
          recommendedInfoWindowRef.current =
            new window.kakao.maps.InfoWindow({
              content: recommendedLabel,
            })
          recommendedInfoWindowRef.current.open(
            map,
            recommendedMarkerRef.current,
          )

          setRouteLoading(true)
          setRouteError('')
          setRouteInfo(null)

          try {
            const route = await getDrivingRoute({
              originLatitude,
              originLongitude,
              destinationLatitude,
              destinationLongitude,
            })

            if (cancelled) return

            const routePath = route.path.map(
              (point) =>
                new window.kakao.maps.LatLng(
                  Number(point.latitude),
                  Number(point.longitude),
                ),
            )

            routePolylineRef.current?.setMap(null)
            routePolylineRef.current =
              new window.kakao.maps.Polyline({
                map,
                path: routePath,
                strokeWeight: 6,
                strokeColor: '#00897b',
                strokeOpacity: 0.85,
                strokeStyle: 'solid',
              })

            const routeBounds =
              new window.kakao.maps.LatLngBounds()
            routePath.forEach((point) => routeBounds.extend(point))
            map.setBounds(routeBounds)

            setRouteInfo({
              distanceM: route.distance_m,
              durationSeconds: route.duration_seconds,
            })
          } catch (error) {
            if (!cancelled) {
              setRouteError(
                error.message || '도로 경로를 불러오지 못했습니다.',
              )
            }
          } finally {
            if (!cancelled) setRouteLoading(false)
          }
        }

        const usePosition = (latitude, longitude) => {
          if (cancelled) return

          const currentPosition = new window.kakao.maps.LatLng(
            latitude,
            longitude,
          )

          searchPositionRef.current = currentPosition
          map.setCenter(currentPosition)

          currentMarkerRef.current?.setMap(null)

          const currentMarkerImage =
            new window.kakao.maps.MarkerImage(
              CURRENT_LOCATION_MARKER_URL,
              new window.kakao.maps.Size(36, 42),
              {
                offset: new window.kakao.maps.Point(18, 42),
              },
            )

          currentMarkerRef.current = new window.kakao.maps.Marker({
            map,
            position: currentPosition,
            image: currentMarkerImage,
            zIndex: 10,
          })

          const currentLocationLabel = document.createElement('div')
          currentLocationLabel.textContent = '현재 위치'
          currentLocationLabel.style.padding = '7px 10px'
          currentLocationLabel.style.fontSize = '13px'
          currentLocationLabel.style.fontWeight = '700'
          currentLocationLabel.style.whiteSpace = 'nowrap'

          currentInfoWindowRef.current?.close()
          currentInfoWindowRef.current =
            new window.kakao.maps.InfoWindow({
              content: currentLocationLabel,
            })
          currentInfoWindowRef.current.open(
            map,
            currentMarkerRef.current,
          )

          setLocationNotice('')
          searchPlaces(initialKeyword, currentPosition)
          drawRecommendedRoute(latitude, longitude)
        }

        if (!navigator.geolocation) {
          setLocationNotice(
            '현재 위치를 확인할 수 없어 서울시청 주변을 검색합니다.',
          )
          searchPlaces(initialKeyword, defaultPosition)
          return
        }

        navigator.geolocation.getCurrentPosition(
          ({ coords }) => usePosition(coords.latitude, coords.longitude),
          () => {
            if (cancelled) return
            setLocationNotice(
              '위치 권한이 없어 서울시청 주변을 검색합니다.',
            )
            searchPlaces(initialKeyword, defaultPosition)
          },
          {
            enableHighAccuracy: false,
            timeout: 10000,
            maximumAge: 300000,
          },
        )
      })
      .catch((error) => {
        if (!cancelled) {
          setMapError(error.message || '지도를 표시하지 못했습니다.')
        }
      })

    return () => {
      cancelled = true
      clearPlaceMarkers()
      currentMarkerRef.current?.setMap(null)
      currentInfoWindowRef.current?.close()
      recommendedMarkerRef.current?.setMap(null)
      recommendedInfoWindowRef.current?.close()
      routePolylineRef.current?.setMap(null)
    }
  }, [initialKeyword])

  const submitSearch = (event) => {
    event.preventDefault()
    searchPlaces(keyword)
  }

  return (
    <div className="container page">
      <PageHead
        title="📍 전문가 기관 추천"
        sub="내 주변의 복지시설을 지도에서 검색해 보세요."
        right={(
          <Link to="/share" className="btn btn-ghost btn-sm">
            ← 나누다
          </Link>
        )}
      />

      <form
        onSubmit={submitSearch}
        className="card card-pad"
        style={{ marginBottom: 'var(--sp-4)' }}
      >
        <div className="row" style={{ gap: 10 }}>
          <input
            type="search"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="복지시설 또는 기관명을 입력하세요"
            aria-label="복지시설 검색어"
            style={{ flex: 1 }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!mapReady || searching}
          >
            {searching ? '검색 중...' : '검색'}
          </button>
        </div>

        {resultCount !== null && (
          <p className="hint" style={{ marginTop: 10 }}>
            검색 결과 {resultCount}곳 · 시설 마커를 누르면 카카오맵 상세정보가 열립니다.
          </p>
        )}
      </form>

      {recommendation && (
        <div
          className="card card-pad"
          style={{ marginBottom: 'var(--sp-4)' }}
        >
          <strong>
            추천 기관: {recommendation.facility_name || initialKeyword}
          </strong>

          {routeLoading && (
            <p className="muted" style={{ marginTop: 8 }}>
              현재 위치에서 추천 기관까지의 도로 경로를 찾고 있습니다.
            </p>
          )}

          {routeInfo && (
            <p className="muted" style={{ marginTop: 8 }}>
              자동차 이동 거리{' '}
              {formatRouteDistance(routeInfo.distanceM)} · 예상 시간{' '}
              {formatRouteDuration(routeInfo.durationSeconds)}
            </p>
          )}

          {routeError && (
            <div className="callout-warn" style={{ marginTop: 10 }}>
              {routeError}
            </div>
          )}
        </div>
      )}

      <section className="card" style={{ overflow: 'hidden' }}>
        <div
          ref={mapElementRef}
          style={{ width: '100%', minHeight: 560 }}
        />

        {mapError && (
          <div className="card-pad callout-warn">{mapError}</div>
        )}

        {locationNotice && !mapError && (
          <div className="card-pad callout-warn">{locationNotice}</div>
        )}
      </section>
    </div>
  )
}
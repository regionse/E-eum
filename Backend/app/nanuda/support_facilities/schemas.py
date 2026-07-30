from pydantic import BaseModel, ConfigDict


class SupportFacilityResponse(BaseModel):
    facility_id: int
    external_id: str | None

    facility_type: str
    facility_category: str | None

    facility_name: str
    address: str | None

    phone: str | None
    website_url: str | None

    source_name: str

    model_config = ConfigDict(
        from_attributes=True,
    )



class KakaoPlaceResponse(BaseModel):
    place_name: str | None
    address: str | None
    phone: str | None
    place_url: str | None
    longitude: str | None
    latitude: str | None


class SupportFacilityMapResponse(BaseModel):
    facility_id: int
    facility_name: str
    db_address: str | None
    db_phone: str | None

    map_found: bool
    place: KakaoPlaceResponse | None
import streamlit as st
import requests  # Ensure requests is available for the SDK
import json
import re
import urllib3
import time
import logging
from typing import (
    Literal,
    Dict,
    Any,
    Optional,
    Tuple,
    Union,
    Mapping,
    List,
    TypedDict,
)  # Added TypedDict


# --- SDK Specific Exceptions (Copy from your SDK file) ---
class TflCycleHireSDKError(Exception):
    pass


class TflCycleHireAPIError(TflCycleHireSDKError):
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class TflCycleHireDataError(TflCycleHireSDKError):
    pass


class TflCycleHireConfigError(TflCycleHireSDKError):
    pass


# --- Configure Logging (Streamlit might handle this differently, but basic setup is good) ---
# For Streamlit, often it's better to let Streamlit handle its own logging,
# but SDK logs can still be useful. We'll use a basic config.
# If you want to see SDK logs in the console where streamlit runs:
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)  # For app-specific logs
sdk_logger = logging.getLogger(
    "TflCycleHireSDK"
)  # Assuming your SDK uses a logger named like this or its module name
sdk_logger.setLevel(logging.INFO)  # Or DEBUG

# --- TypedDicts (Copy from your SDK file) ---
StaticallyDefinedLocationKey = Literal[
    "cromer_street", "taviton_street", "warren_street_station"
]

SearchedStationInfo = TypedDict(
    "SearchedStationInfo",
    {
        "station_id": str,
        "name": str,
        "subtitle": str,
        "terminal_name": Optional[str],
        "point_name": str,
        "dock_location": Optional[str],
    },
)

# --- DEFAULT_LOCATION_DATA (Copy from your SDK file) ---
DEFAULT_LOCATION_DATA: Dict[StaticallyDefinedLocationKey, Dict[str, str]] = {
    "cromer_street": {
        "terminal_name": "300205",
        "point_name": "Cromer Street, Bloomsbury",
        "c3_encoding": "Kv6OJKA1JWRui1R+UltG2iCZBcb3+EMMfBu5aAhZNEXnA3QTJHKcKBLT+Hd097N5",
        "c3_clienttime": "1748480905.359684",
    },
    "taviton_street": {
        "terminal_name": "001009",
        "point_name": "Taviton Street, Bloomsbury",
        "c3_encoding": "hjQd5cl1SN7BOdmflRPMZwu1UnranBQaYc1W+u/ofJSmJa24Ca9fbkVYjg5SZ+Lg",
        "c3_clienttime": "1748481522.599196",
    },
    "warren_street_station": {
        "terminal_name": "001090",
        "point_name": "Warren Street Station, Euston",
        "c3_encoding": "Af1F2GlMLbIbykRF6YQQbhJQxCWXYsXyOdUx4M2KxIAvFtrFbaK3CmUhY1dwxDa0",
        "c3_clienttime": "1748481544.979739",
    },
}


# --- TflCycleHireSDK Class (Paste your entire SDK class definition here) ---
# For brevity, I'm assuming it's defined above or in an importable module.
# Ensure it's the LATEST version that includes search_stations with smart token handling.
class TflCycleHireSDK:
    BASE_URL_WORKFLOWS = (
        "https://ce-a22.corethree.net/Workflows/HandleEventWithNode?format=json"
    )
    BASE_URL_CLIENTS_TFL = "https://ce-a22.corethree.net/Clients/TfL"  # For search

    DEFAULT_CONFIG = {
        "user_agent": "Core/202503171232 (iOS; iPad14,1; iPadOS 18.3.2; uk.gov.tfl.cyclehire)",
        "accept_language": "en-SG,en-GB;q=0.9,en;q=0.8",
        "c3_language": "en",
        "c3_applysensitivedatacheck": "y",
        "c3_scalefactor": "2.00",
        "c3_capabilities": "inlinevouchers,expirytags,bucketpopulation,vzero,creditcall-chipdna,card.io,camera,camera-front,camera-rear,ble-unknown,location-on-wheninuse,londonriders,londonridersphase2r1,londonridersphase3,londonridersphase4,3dsenabled,ebikesphase2,daypass",
        "c3_batterylevel": "-1.000000",
        "c3_userlat": "51.5282",
        "c3_userlong": "-0.121092",
        "c3_deviceid": "555D91A6-5B1E-49BC-9624-1989B4DA4833",
        "event_name": "Click",
        "c3_controlvals": "cHTnp0wCbVOhbs12x8sR4+2I/8CVACvEd8Zn5e3Tpas=",
    }
    DEFAULT_C3_USERAUTH = "564e7ff6ebbf80c4cafb4c7b7d3ea7bbc4435ad0|bcSxLxDWpaTC"

    NODE_XML_TEMPLATE_CONFIRM_HIRE = """<Node Type%3D"Node.FormControls.Button" ID%3D"page_button1" SortOrder%3D"25" TTL%3D"3600" AliasMode%3D"Passive">
<Name>Confirm hire<%2FName>
<TreeMode>Leaf<%2FTreeMode>
<Language><%2FLanguage>
<TargetUri>part%3A%2F%2FClients.TfL.EBikePhase2.ConfirmMemberHire%3FTerminalName%3D{terminal_name}%26amp%3BPointName%3D{point_name_encoded}%26amp%3BLCHS_Confirm%3D1%26amp%3BnbBikes%3D(null)<%2FTargetUri>
<Tags>
<Tag key%3D"Style.Cell.ForegroundColor">#FFFFFF<%2FTag>
<Tag key%3D"Style.Cell.BorderColor">#EE0000<%2FTag>
<Tag key%3D"Style.Cell.CenterVertically">1<%2FTag>
<Tag key%3D"Style.Cell.TextAlign">center<%2FTag>
<Tag key%3D"Style.Cell.BackgroundBorderRadius">5%<%2FTag>
<Tag key%3D"Style.Cell.Width">70%<%2FTag>
<Tag key%3D"Style.Cell.Margin.BackgroundColor">#FFFFFF<%2FTag>
<Tag key%3D"Style.Cell.BackgroundColor">#EE0000<%2FTag>
<Tag key%3D"Style.Cell.BorderWidth">1px<%2FTag>
<Tag key%3D"Style.Cell.HideNativeWidgets">1<%2FTag>
<Tag key%3D"Style.Cell.Margin">50 40 40 40<%2FTag>
<Tag key%3D"Style.Cell.FontSize">16px<%2FTag>
<Tag key%3D"Style.Class">button_set page_button1<%2FTag>
<Tag key%3D"Style.Cell.FontName">NJFont-Medium<%2FTag>
<%2FTags>
<%2FNode>"""

    def __init__(
        self,
        c3_userauth: str = DEFAULT_C3_USERAUTH,
        static_location_data_map: Optional[
            Mapping[StaticallyDefinedLocationKey, Dict[str, str]]
        ] = None,
        sdk_config: Optional[Dict[str, Any]] = None,
        disable_ssl_warnings: bool = True,
        session: Optional[requests.Session] = None,
    ):
        self.c3_userauth = c3_userauth
        self.config = {**self.DEFAULT_CONFIG, **(sdk_config or {})}
        self.static_location_data = dict(
            static_location_data_map or DEFAULT_LOCATION_DATA
        )

        if disable_ssl_warnings:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.config["user_agent"]

        self._active_c3_encoding: Optional[str] = None
        self._active_original_c3_clienttime: Optional[str] = None
        self._active_token_source_info: Optional[str] = None

        sdk_logger.info(
            f"SDK initialized. UserAuth (partial): {self.c3_userauth[:10]}..."
        )  # Use sdk_logger

    @property
    def active_token_info(self) -> Dict[str, Optional[str]]:
        return {
            "c3_encoding": self._active_c3_encoding,
            "original_c3_clienttime": self._active_original_c3_clienttime,
            "source": self._active_token_source_info,
        }

    def prime_tokens_from_static_location(
        self, location_key: StaticallyDefinedLocationKey
    ) -> bool:
        if location_key not in self.static_location_data:
            sdk_logger.error(
                f"Cannot prime tokens: Static Location key '{location_key}' not found."
            )
            return False
        loc_details = self.static_location_data[location_key]
        if "c3_encoding" in loc_details and "c3_clienttime" in loc_details:
            self._active_c3_encoding = loc_details["c3_encoding"]
            self._active_original_c3_clienttime = loc_details["c3_clienttime"]
            self._active_token_source_info = f"static_example_for_{location_key}"
            sdk_logger.info(
                f"SDK active tokens primed from static data for '{location_key}'."
            )
            return True
        else:
            sdk_logger.warning(
                f"Cannot prime tokens: Missing token data for '{location_key}' in static_location_data."
            )
            return False

    def set_active_tokens(
        self,
        c3_encoding: str,
        original_c3_clienttime: str,
        source_info: str = "user_set",
    ):
        self._active_c3_encoding = c3_encoding
        self._active_original_c3_clienttime = original_c3_clienttime
        self._active_token_source_info = source_info
        sdk_logger.info(f"SDK active tokens explicitly set. Source: {source_info}.")

    def clear_active_tokens(self):
        self._active_c3_encoding = None
        self._active_original_c3_clienttime = None
        self._active_token_source_info = None
        sdk_logger.info("SDK active tokens cleared.")

    def _build_confirm_hire_node_xml(
        self, terminal_name: str, point_name_display: str
    ) -> str:
        point_name_encoded = point_name_display.replace(",", "%2C")
        return self.NODE_XML_TEMPLATE_CONFIRM_HIRE.format(
            terminal_name=terminal_name, point_name_encoded=point_name_encoded
        )

    def _execute_confirm_hire_api_call(
        self,
        terminal_name: str,
        point_name: str,
        c3_encoding: str,
        c3_clienttime: str,
        timeout: int,
    ) -> str:
        headers = {
            "Host": "ce-a22.corethree.net",
            "Accept": "*/*",
            "c3-encoding": c3_encoding,
            "Accept-Language": self.config["accept_language"],
        }
        node_xml = self._build_confirm_hire_node_xml(terminal_name, point_name)
        payload = {
            "c3-clienttime": c3_clienttime,
            "c3-language": self.config["c3_language"],
            "c3-applysensitivedatacheck": self.config["c3_applysensitivedatacheck"],
            "c3-scalefactor": self.config["c3_scalefactor"],
            "Node": node_xml,
            "c3-capabilities": self.config["c3_capabilities"],
            "c3-batterylevel": self.config["c3_batterylevel"],
            "c3-userlat": self.config["c3_userlat"],
            "c3-deviceid": self.config["c3_deviceid"],
            "c3-userlong": self.config["c3_userlong"],
            "Event": self.config["event_name"],
            "c3-controlvals": self.config["c3_controlvals"],
            "c3-userauth": self.c3_userauth,
        }
        sdk_logger.debug(
            f"Executing Confirm Hire API call for: {point_name} (Terminal: {terminal_name})"
        )
        response_obj = None
        try:
            response_obj = self.session.post(
                self.BASE_URL_WORKFLOWS,
                headers=headers,
                data=payload,
                verify=False,
                timeout=timeout,
            )
            response_obj.raise_for_status()
            data = response_obj.json()
        except requests.exceptions.HTTPError as http_err:
            raise TflCycleHireAPIError(
                str(http_err),
                getattr(http_err.response, "status_code", None),
                getattr(http_err.response, "text", None),
            ) from http_err
        except requests.exceptions.RequestException as req_err:
            raise TflCycleHireSDKError(f"Request failed: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise TflCycleHireAPIError(
                "Failed to decode JSON response.",
                getattr(response_obj, "status_code", None),
                getattr(response_obj, "text", None),
            ) from json_err

        release_code_found: Optional[str] = None
        children = data.get("Children", [])
        for child in children:
            if (
                child.get("Name") == "Your cycle hire release code:"
                and "Subtitle" in child
            ):
                release_code_found = child.get("Subtitle")
                break
        if not release_code_found:
            for child in children:
                if child.get("ID", "").endswith("_unlockbar") and "Name" in child:
                    match = re.search(r"Release code (\d+)", child.get("Name", ""))
                    if match:
                        release_code_found = match.group(1)
                        break
        if release_code_found:
            return release_code_found
        else:
            raise TflCycleHireDataError(
                f"Could not find release code for {point_name}."
            )

    def get_release_code_with_explicit_tokens(
        self,
        terminal_name: str,
        point_name: str,
        c3_encoding: str,
        c3_clienttime: str,
        timeout: int = 20,
        update_active_tokens_on_success: bool = True,
    ) -> str:
        sdk_logger.info(
            f"Attempting code retrieval for '{point_name}' (Terminal: {terminal_name}) with explicit tokens."
        )
        code = self._execute_confirm_hire_api_call(
            terminal_name, point_name, c3_encoding, c3_clienttime, timeout
        )
        if update_active_tokens_on_success:
            self.set_active_tokens(
                c3_encoding, c3_clienttime, f"explicit_call_for_{point_name}"
            )
        return code

    def get_release_code_for_static_location(
        self,
        location_key: StaticallyDefinedLocationKey,
        timeout: int = 20,
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
        try_static_location_tokens: bool = True,
    ) -> str:
        sdk_logger.info(
            f"Smart attempt for release code at static location '{location_key}'."
        )
        last_error: Optional[Exception] = None
        if location_key not in self.static_location_data:
            raise TflCycleHireConfigError(
                f"Static location key '{location_key}' not found."
            )
        target_loc_details = self.static_location_data[location_key]
        target_terminal_name = target_loc_details["terminal_name"]
        target_point_name = target_loc_details["point_name"]

        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            sdk_logger.info("Strategy: Trying active SDK tokens (original time).")
            try:
                return self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
            except Exception as e:
                sdk_logger.warning(f"Strategy (active original time) failed: {e}")
                last_error = e

        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            sdk_logger.info(
                f"Strategy: Trying active SDK encoding with FRESH time ({fresh_client_time})."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    fresh_client_time,
                    timeout,
                )
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_static_{location_key}",
                )
                return code
            except Exception as e:
                sdk_logger.warning(f"Strategy (active fresh time) failed: {e}")
                last_error = e

        if try_static_location_tokens:
            if (
                "c3_encoding" in target_loc_details
                and "c3_clienttime" in target_loc_details
            ):
                sdk_logger.info(
                    f"Strategy: Trying static/example tokens for target static location '{location_key}'."
                )
                try:
                    code = self._execute_confirm_hire_api_call(
                        target_terminal_name,
                        target_point_name,
                        target_loc_details["c3_encoding"],
                        target_loc_details["c3_clienttime"],
                        timeout,
                    )
                    self.set_active_tokens(
                        target_loc_details["c3_encoding"],
                        target_loc_details["c3_clienttime"],
                        f"static_example_for_{location_key}",
                    )
                    return code
                except Exception as e:
                    sdk_logger.warning(f"Strategy (static location tokens) failed: {e}")
                    last_error = e
            else:
                sdk_logger.warning(
                    f"Strategy (static location tokens): Missing token data for '{location_key}'."
                )

        final_msg = f"All token strategies failed for static location '{location_key}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            raise TflCycleHireConfigError(
                final_msg + " No valid strategies enabled or configured."
            )

    def _execute_search_api_call(
        self, search_text: str, c3_encoding: str, c3_clienttime: str, timeout: int
    ) -> List[SearchedStationInfo]:
        search_url = f"{self.BASE_URL_CLIENTS_TFL}/GenerateLCHSDynamicSearch"
        headers = {
            "Host": "ce-a22.corethree.net",
            "Accept": "*/*",
            "c3-encoding": c3_encoding,
            "Accept-Language": self.config["accept_language"],
        }
        payload = {
            "c3-clienttime": c3_clienttime,
            "c3-scalefactor": self.config["c3_scalefactor"],
            "c3-userlat": self.config["c3_userlat"],
            "c3-userlong": self.config["c3_userlong"],
            "c3-batterylevel": self.config["c3_batterylevel"],
            "c3-language": self.config["c3_language"],
            "c3-applysensitivedatacheck": self.config["c3_applysensitivedatacheck"],
            "c3-userauth": self.c3_userauth,
            "c3-controlvals": self.config["c3_controlvals"],
            "c3-capabilities": self.config["c3_capabilities"],
            "c3-deviceid": self.config["c3_deviceid"],
            "lchs_search_text": search_text,
            "postback": "1",
            "format": "json",
        }
        sdk_logger.debug(f"Executing Search API call for: '{search_text}'")
        response_obj = None
        try:
            response_obj = self.session.post(
                search_url, headers=headers, data=payload, verify=False, timeout=timeout
            )
            response_obj.raise_for_status()
            data = response_obj.json()
        except requests.exceptions.HTTPError as http_err:
            raise TflCycleHireAPIError(
                str(http_err),
                getattr(http_err.response, "status_code", None),
                getattr(http_err.response, "text", None),
            ) from http_err
        except Exception as e:
            raise TflCycleHireSDKError(
                f"Search station API call unexpected error: {e}"
            ) from e
        results: List[SearchedStationInfo] = []
        children = data.get("Children", [])
        station_data_aggregator: Dict[str, Dict[str, Any]] = {}
        for child in children:
            child_type = child.get("Type")
            child_id_str = child.get("ID", "")
            id_match = re.match(r"^(lchs_searchresult_(\d+))", child_id_str)
            if not id_match:
                continue
            station_id_prefix = id_match.group(1)
            parsed_station_id = id_match.group(2)
            if station_id_prefix not in station_data_aggregator:
                station_data_aggregator[station_id_prefix] = {
                    "raw_station_id_from_id": parsed_station_id
                }
            current_station_entry = station_data_aggregator[station_id_prefix]
            if child_type == "Node.Link":
                current_station_entry["name"] = child.get("Name")
                current_station_entry["subtitle"] = child.get("Subtitle")
                tags = child.get("Tags", {})
                current_station_entry["dock_location"] = tags.get("LCHS.DockLocation")
                if tags.get("LCHS.StationID"):
                    current_station_entry["station_id_from_link_tags"] = tags.get(
                        "LCHS.StationID"
                    )
            elif child_type == "Node.Media.Image" and child.get("Name") == "Hire now":
                tags = child.get("Tags", {})
                current_station_entry["terminal_name_from_image_tags"] = tags.get(
                    "Terminal"
                )
                current_station_entry["point_name_from_image_tags"] = tags.get(
                    "PointName"
                )
                if tags.get("StationID"):
                    current_station_entry["station_id_from_image_tags"] = tags.get(
                        "StationID"
                    )
        for prefix, collected_details in station_data_aggregator.items():
            station_id = (
                collected_details.get("station_id_from_image_tags")
                or collected_details.get("station_id_from_link_tags")
                or collected_details.get("raw_station_id_from_id")
            )
            name = collected_details.get("name")
            point_name = collected_details.get("point_name_from_image_tags") or name
            terminal_name = collected_details.get("terminal_name_from_image_tags")
            if station_id and name and point_name:
                results.append({"station_id": station_id, "name": name, "subtitle": collected_details.get("subtitle", "N/A"), "terminal_name": terminal_name, "point_name": point_name, "dock_location": collected_details.get("dock_location")})  # type: ignore
            else:
                sdk_logger.warning(
                    f"Skipping search result (prefix {prefix}): missing core data: {collected_details}"
                )
        return results

    def search_stations(
        self,
        search_text: str,
        timeout: int = 15,
        c3_encoding_override: Optional[str] = None,
        c3_clienttime_override: Optional[str] = None,
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
        prime_from_static_if_no_active: Optional[StaticallyDefinedLocationKey] = None,
    ) -> List[SearchedStationInfo]:
        sdk_logger.info(f"Smart search for stations: '{search_text}'")
        last_error: Optional[Exception] = None
        if c3_encoding_override and c3_clienttime_override:
            sdk_logger.info(
                "Strategy (Search): Using EXPLICITLY provided override tokens."
            )
            try:
                results = self._execute_search_api_call(
                    search_text, c3_encoding_override, c3_clienttime_override, timeout
                )
                self.set_active_tokens(
                    c3_encoding_override,
                    c3_clienttime_override,
                    f"explicit_override_for_search_{search_text}",
                )
                sdk_logger.info(
                    f"Search successful with explicit tokens. Found {len(results)} stations."
                )
                return results
            except Exception as e:
                sdk_logger.error(f"Strategy (explicit override for search) failed: {e}")
                raise TflCycleHireSDKError(
                    f"Explicit token override failed for search '{search_text}'."
                ) from e
        if prime_from_static_if_no_active and not self._active_c3_encoding:
            sdk_logger.info(
                f"No active SDK tokens. Priming from static location '{prime_from_static_if_no_active}' for search."
            )
            if not self.prime_tokens_from_static_location(
                prime_from_static_if_no_active
            ):
                sdk_logger.warning(
                    f"Failed to prime tokens from '{prime_from_static_if_no_active}'."
                )
        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            sdk_logger.info(
                "Strategy (Search): Trying active SDK tokens (original time)."
            )
            try:
                results = self._execute_search_api_call(
                    search_text,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
                sdk_logger.info(
                    f"Search successful with active (original time) tokens. Found {len(results)} stations."
                )
                return results
            except Exception as e:
                sdk_logger.warning(
                    f"Strategy (active original time for search) failed: {e}"
                )
                last_error = e
        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            sdk_logger.info(
                f"Strategy (Search): Trying active SDK encoding with FRESH time ({fresh_client_time})."
            )
            try:
                results = self._execute_search_api_call(
                    search_text, self._active_c3_encoding, fresh_client_time, timeout
                )
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_search_{search_text}",
                )
                sdk_logger.info(
                    f"Search successful with active encoding (fresh time). Found {len(results)} stations."
                )
                return results
            except Exception as e:
                sdk_logger.warning(
                    f"Strategy (active fresh time for search) failed: {e}"
                )
                last_error = e
        final_msg = f"All token strategies failed for search_stations with query '{search_text}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            raise TflCycleHireConfigError(
                final_msg
                + " No token strategies enabled or active/primeable tokens available."
            )

    def get_release_code_for_searched_station(
        self,
        station_info: SearchedStationInfo,
        timeout: int = 20,
        c3_encoding_override: Optional[str] = None,
        c3_clienttime_override: Optional[str] = None,
        try_active_original_time: bool = True,
        try_active_fresh_time: bool = True,
    ) -> str:
        sdk_logger.info(
            f"Attempting release code for searched station: '{station_info['name']}' (ID: {station_info['station_id']})"
        )
        if not station_info.get("terminal_name"):
            raise TflCycleHireConfigError(
                f"Cannot get code for '{station_info['name']}': TerminalName missing."
            )
        target_terminal_name = station_info["terminal_name"]
        target_point_name = station_info["point_name"]
        last_error: Optional[Exception] = None
        if c3_encoding_override and c3_clienttime_override:
            sdk_logger.info(
                "Strategy: Using EXPLICIT override tokens for searched station."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    c3_encoding_override,
                    c3_clienttime_override,
                    timeout,
                )
                self.set_active_tokens(
                    c3_encoding_override,
                    c3_clienttime_override,
                    f"override_for_{station_info['name']}",
                )
                return code
            except Exception as e:
                sdk_logger.error(f"Strategy (explicit override) failed: {e}")
                raise TflCycleHireSDKError(
                    f"Explicit token override failed for {station_info['name']}."
                ) from e
        if (
            try_active_original_time
            and self._active_c3_encoding
            and self._active_original_c3_clienttime
        ):
            sdk_logger.info(
                "Strategy: Trying active SDK tokens (original time) for searched station."
            )
            try:
                return self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    self._active_original_c3_clienttime,
                    timeout,
                )
            except Exception as e:
                sdk_logger.warning(f"Strategy (active original time) failed: {e}")
                last_error = e
        if try_active_fresh_time and self._active_c3_encoding:
            fresh_client_time = f"{time.time():.6f}"
            sdk_logger.info(
                f"Strategy: Trying active SDK encoding with FRESH time ({fresh_client_time}) for searched station."
            )
            try:
                code = self._execute_confirm_hire_api_call(
                    target_terminal_name,
                    target_point_name,
                    self._active_c3_encoding,
                    fresh_client_time,
                    timeout,
                )
                self.set_active_tokens(
                    self._active_c3_encoding,
                    fresh_client_time,
                    f"active_encoding_fresh_time_for_searched_{station_info['name']}",
                )
                return code
            except Exception as e:
                sdk_logger.warning(f"Strategy (active fresh time) failed: {e}")
                last_error = e
        final_msg = f"All smart token strategies failed for searched station '{station_info['name']}'."
        if last_error:
            raise TflCycleHireSDKError(final_msg) from last_error
        else:
            raise TflCycleHireConfigError(
                final_msg + " No token strategies enabled or active tokens available."
            )


# --- END OF TflCycleHireSDK Class ---


# --- Streamlit App ---
def get_sdk_instance() -> TflCycleHireSDK:
    """Initializes or retrieves the SDK instance from session state."""
    if "sdk" not in st.session_state:
        st.session_state.sdk = TflCycleHireSDK()
        # Optionally, prime tokens on first load if desired
        # st.session_state.sdk.prime_tokens_from_static_location("cromer_street")
    return st.session_state.sdk


def main_app():
    st.set_page_config(page_title="TfL Cycle Hire Assistant", layout="wide")
    st.title("🚲 TfL Cycle Hire Assistant (Experimental)")
    st.markdown(
        """
    This app uses an experimental SDK to interact with certain TfL Cycle Hire API functions.
    **IMPORTANT:** The token reusability observed is based on limited tests with specific example tokens
    and is **NOT GUARANTEED** to work long-term or for all users/tokens.
    """
    )

    sdk = get_sdk_instance()

    # --- Sidebar for SDK State and Token Management ---
    with st.sidebar:
        st.header("SDK Token Management")
        st.caption("Controls the SDK's active `c3_encoding` and `c3_clienttime`.")

        active_tokens = sdk.active_token_info
        if active_tokens.get("c3_encoding"):
            st.success(
                f"Active Encoding (partial): `{active_tokens['c3_encoding'][:15]}...`"
            )
            st.caption(
                f"Original ClientTime: `{active_tokens['original_c3_clienttime']}`"
            )
            st.caption(f"Source: `{active_tokens['source']}`")
        else:
            st.info("No active tokens set in SDK.")

        st.subheader("Prime Active Tokens from Static Data")
        static_loc_to_prime = st.selectbox(
            "Select static location to prime tokens from:",
            options=list(sdk.static_location_data.keys()),
            key="prime_loc_select",
        )
        if st.button("Prime Tokens", key="prime_button"):
            if sdk.prime_tokens_from_static_location(static_loc_to_prime):  # type: ignore
                st.success(f"SDK tokens primed from {static_loc_to_prime}.")
                st.experimental_rerun()  # Rerun to update display
            else:
                st.error("Failed to prime tokens.")

        if st.button("Clear Active Tokens", key="clear_tokens_button"):
            sdk.clear_active_tokens()
            st.info("Active SDK tokens cleared.")
            st.experimental_rerun()

        st.markdown("---")
        st.subheader("Explicitly Set Active Tokens")
        exp_c3_encoding = st.text_input("c3_encoding (for SDK)", key="exp_enc_sdk")
        exp_c3_clienttime = st.text_input("c3_clienttime (for SDK)", key="exp_time_sdk")
        if st.button("Set These Active Tokens", key="set_exp_tokens_sdk"):
            if exp_c3_encoding and exp_c3_clienttime:
                sdk.set_active_tokens(
                    exp_c3_encoding, exp_c3_clienttime, "streamlit_explicit_set"
                )
                st.success("Explicit tokens set as active in SDK.")
                st.experimental_rerun()
            else:
                st.warning("Both encoding and client time must be provided.")

    # --- Main App Area ---
    col1, col2 = st.columns(2)

    with col1:
        st.header("Search Stations")
        search_query = st.text_input(
            "Enter station name or area (e.g., 'King', 'Holborn')", key="search_query"
        )

        # Option to provide explicit tokens for the search action itself
        st.markdown(
            "<small>Optional: Override tokens for this search action</small>",
            unsafe_allow_html=True,
        )
        search_override_expander = st.expander("Search Token Overrides")
        with search_override_expander:
            search_c3_enc_override = st.text_input(
                "Search c3_encoding override", key="search_enc_override"
            )
            search_c3_time_override = st.text_input(
                "Search c3_clienttime override", key="search_time_override"
            )

        if st.button("Search", key="search_button"):
            if not search_query:
                st.warning("Please enter a search query.")
            else:
                with st.spinner(f"Searching for '{search_query}'..."):
                    try:
                        # Use override tokens if provided, otherwise SDK uses its smart strategy
                        # (which might use active tokens or need priming)
                        if search_c3_enc_override and search_c3_time_override:
                            results = sdk.search_stations(
                                search_query,
                                c3_encoding_override=search_c3_enc_override,
                                c3_clienttime_override=search_c3_time_override,
                            )
                        else:
                            # If no active tokens, tell search to try priming from a default
                            results = sdk.search_stations(
                                search_query,
                                prime_from_static_if_no_active="cromer_street",
                            )

                        st.session_state.search_results = (
                            results  # Store in session state
                        )
                        if not results:
                            st.info(f"No stations found for '{search_query}'.")
                        st.experimental_rerun()  # Rerun to display results
                    except TflCycleHireSDKError as e:
                        st.error(f"Search failed: {e}")
                        st.session_state.search_results = []  # Clear old results
                    except Exception as e:
                        st.error(f"An unexpected error occurred during search: {e}")
                        st.session_state.search_results = []

        if "search_results" in st.session_state and st.session_state.search_results:
            st.subheader("Search Results")
            results = st.session_state.search_results

            hirable_stations = [res for res in results if res["terminal_name"]]

            if not hirable_stations:
                st.info(
                    "No directly hirable stations found in search results (missing TerminalName)."
                )
            else:
                # Create display names for the selectbox
                station_options = {
                    f"{res['name']} ({res['subtitle']})": res
                    for res in hirable_stations
                }
                selected_station_display_name = st.selectbox(
                    "Select a hirable station from search:",
                    options=list(station_options.keys()),
                    key="searched_station_select",
                )

                if selected_station_display_name:
                    selected_searched_station: SearchedStationInfo = station_options[
                        selected_station_display_name
                    ]
                    st.session_state.selected_searched_station_obj = (
                        selected_searched_station  # Store the object
                    )

                    if st.button(
                        "Get Code for Searched Station", key="get_code_searched"
                    ):
                        with st.spinner(
                            f"Getting code for {selected_searched_station['name']}..."
                        ):
                            try:
                                # This method uses SDK's active token strategies
                                code = sdk.get_release_code_for_searched_station(
                                    selected_searched_station
                                )
                                st.success(
                                    f"Release Code for {selected_searched_station['name']}: **{code}**"
                                )
                                st.balloons()
                            except TflCycleHireSDKError as e:
                                st.error(f"Failed to get code: {e}")
                            except Exception as e:
                                st.error(f"An unexpected error: {e}")
        elif (
            "search_results" in st.session_state and not st.session_state.search_results
        ):  # Search was run but no results
            pass  # Message already shown by search button logic

    with col2:
        st.header("Get Code for Static Location")
        static_loc_options = list(sdk.static_location_data.keys())
        selected_static_loc_key = st.selectbox(
            "Select a pre-defined static location:",
            options=static_loc_options,
            key="static_loc_select",
        )

        if st.button("Get Code for Static Location", key="get_code_static"):
            if selected_static_loc_key:
                loc_name = sdk.static_location_data[selected_static_loc_key]["point_name"]  # type: ignore
                with st.spinner(f"Getting code for {loc_name}..."):
                    try:
                        # This method uses SDK's active token strategies + static fallback
                        code = sdk.get_release_code_for_static_location(selected_static_loc_key)  # type: ignore
                        st.success(f"Release Code for {loc_name}: **{code}**")
                        st.balloons()
                    except TflCycleHireSDKError as e:
                        st.error(f"Failed to get code: {e}")
                    except Exception as e:
                        st.error(f"An unexpected error: {e}")
    st.markdown("---")
    st.caption(
        "App uses an SDK that relies on observed API behavior. Functionality may change."
    )


if __name__ == "__main__":
    main_app()

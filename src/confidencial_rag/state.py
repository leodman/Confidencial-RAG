from enum import StrEnum
class SystemState(StrEnum):
    OFF='off'; STARTING='starting'; EMPTY='empty'; LOADING='loading'; READY='ready'; INGESTING='ingesting'; INDEXING='indexing'; CHATTING='chatting'; SAVING='saving'; EXPORTING='exporting'; IMPORTING='importing'; SHUTTING_DOWN='shutting_down'; ERROR='error'

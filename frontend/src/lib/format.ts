import type { BookingStatus, Kind } from '../api/types'
export const kinds: Record<Kind,string> = { private: '一对一私教', group: '小班课' }
export const statuses: Record<BookingStatus,string> = { booked:'已预约',completed:'已完课',cancelled:'已取消',no_show_charged:'缺席已消课',no_show_waived:'缺席免消课' }
export function date(value: string, options: Intl.DateTimeFormatOptions = {}) {
  return new Intl.DateTimeFormat('zh-CN',{ timeZone:'Asia/Shanghai',month:'long',day:'numeric',...options }).format(new Date(value.length===10 ? value+'T12:00:00+08:00' : value))
}
export function time(value: string) { return date(value,{month:undefined,day:undefined,hour:'2-digit',minute:'2-digit',hour12:false}) }
export function today() { return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()) }
export function localTime(value: string) { return value+':00+08:00' }

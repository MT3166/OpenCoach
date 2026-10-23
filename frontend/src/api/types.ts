export type Role = 'coach' | 'student'
export type Kind = 'private' | 'group'
export type BookingStatus = 'booked' | 'completed' | 'cancelled' | 'no_show_charged' | 'no_show_waived'
export interface User { id: number; username: string; display_name: string; role: Role }
export interface SessionState { user: User | null; brand: { display_name: string; coach_name: string }; csrf_token: string }
export interface Student { id: number; name: string; registered: boolean }
export interface Wallet { kind: Kind; label: string; remaining: number; reserved: number; available: number; expired: number; expiring: { expires_on: string; units: number }[] }
export interface Page<T> { items: T[]; pagination: { page: number; page_size: number; total: number } }
export interface Exercise { name: string; sets: number | null; reps: number | null; weight: string | null; duration: number | null }
export interface Course { id: number; title: string; kind: Kind; start: string; end: string; location: string; capacity: number; occupied: number; slots_left: number; cancelled: boolean; my_booking_id: number | null; my_waitlist_id: number | null }
export interface Booking { id: number; status: BookingStatus; session: Course; student?: Student; can_cancel: boolean; can_finish: boolean }
export interface Lesson { source: 'direct' | 'booking'; id: number; student: Student; kind: Kind; occurred_on: string; exercises: Exercise[]; note: string }
export interface LessonResult { lesson: Lesson; wallets: Wallet[] }
export interface Credit { id: number; kind: Kind; entry_type: 'purchase' | 'consume'; units: number; booking_id: number | null; direct_lesson_id: number | null; created_at: string; title: string; expires_on: string | null }
export interface Submission { id: number; exercises: Exercise[]; note: string; submitted_at: string | null; feedback: string; reviewed_at: string | null; updated_at: string }
export interface Plan { id: number; title: string; due_date: string; exercises: Exercise[]; note: string; booking_id: number | null; status: 'pending' | 'draft' | 'submitted' | 'reviewed'; student?: Student; submission: Submission | null }
export interface Attendance { period: string; scheduled_attended: number; scheduled_missed: number; scheduled_cancelled: number; pending: number; direct_attended: number; scheduled_rate: number | null }
export interface StudentDetail { student: Student; wallets: Wallet[]; attendance: Attendance }
export interface Record { id: number; booking_id: number; exercises: Exercise[]; note: string; updated_at: string }
export interface BookingDetail { booking: Booking; student: Student; record: Record | null }
export interface CoachDashboard { today: string; student_count: number; booking_count: number; sessions: Course[]; pending_count: number; pending: { submission_id: number; plan_id: number; student_name: string; title: string }[]; unconfirmed_count: number; unconfirmed: Booking[]; recorded_today: number; recent_lessons: Lesson[] }
export interface StudentDashboard { today: string; student: Student; wallets: Wallet[]; upcoming: Booking[]; plans: Plan[]; completed_count: number; recent_lessons: Lesson[] }
export interface WaitlistEntry { id: number; status: 'waiting' | 'promoted' | 'cancelled'; session: Course; student?: Student; created_at: string; position: number | null; promoted_at: string | null; booking_id: number | null }
export interface MonthlyReport { month: string; scheduled_attended: number; scheduled_missed: number; scheduled_cancelled: number; pending: number; direct_attended: number; waitlist_promoted: number; credit_expired: number; scheduled_rate: number; scheduled_denominator: number }
export interface BatchResult { items: Lesson[]; wallets: { student_id: number; wallets: Wallet[] }[] }

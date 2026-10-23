import { createRouter, createWebHistory } from 'vue-router'
import { ensureSession, session } from './state/session'
const router = createRouter({ history:createWebHistory(), routes:[
  { path:'/',redirect:() => session.value?.user?.role==='coach'?'/coach/':session.value?.user?'/student/':'/login/' },
  { path:'/login/',component:()=>import('./pages/LoginPage.vue') },
  { path:'/invite/:token/',component:()=>import('./pages/InvitePage.vue') },
  { path:'/coach/',component:()=>import('./pages/CoachDashboard.vue'),meta:{role:'coach'} },
  { path:'/coach/reports/',component:()=>import('./pages/CoachReport.vue'),meta:{role:'coach'} },
  { path:'/coach/lessons/batch/',component:()=>import('./pages/CoachBatch.vue'),meta:{role:'coach'} },
  { path:'/coach/lessons/new/',component:()=>import('./pages/CoachRecord.vue'),meta:{role:'coach'} },
  { path:'/coach/lessons/',component:()=>import('./pages/CoachHistory.vue'),meta:{role:'coach'} },
  { path:'/coach/lessons/:id(\\d+)/',component:()=>import('./pages/CoachLesson.vue'),meta:{role:'coach'} },
  { path:'/coach/students/',component:()=>import('./pages/CoachStudents.vue'),meta:{role:'coach'} },
  { path:'/coach/students/:id(\\d+)/',component:()=>import('./pages/CoachStudent.vue'),meta:{role:'coach'} },
  { path:'/coach/sessions/',component:()=>import('./pages/CoachSessions.vue'),meta:{role:'coach'} },
  { path:'/coach/sessions/:id(\\d+)/',component:()=>import('./pages/CoachSession.vue'),meta:{role:'coach'} },
  { path:'/coach/bookings/',component:()=>import('./pages/CoachBookings.vue'),meta:{role:'coach'} },
  { path:'/coach/bookings/:id(\\d+)/',component:()=>import('./pages/CoachBooking.vue'),meta:{role:'coach'} },
  { path:'/coach/plans/',component:()=>import('./pages/CoachPlans.vue'),meta:{role:'coach'} },
  { path:'/coach/plans/:id(\\d+)/',component:()=>import('./pages/CoachPlan.vue'),meta:{role:'coach'} },
  { path:'/student/',component:()=>import('./pages/StudentDashboard.vue'),meta:{role:'student'} },
  { path:'/student/sessions/',component:()=>import('./pages/StudentSessions.vue'),meta:{role:'student'} },
  { path:'/student/bookings/',component:()=>import('./pages/StudentBookings.vue'),meta:{role:'student'} },
  { path:'/student/profile/',component:()=>import('./pages/StudentProfile.vue'),meta:{role:'student'} },
  { path:'/student/training/',component:()=>import('./pages/StudentTraining.vue'),meta:{role:'student'} },
  { path:'/student/plans/:id(\\d+)/',component:()=>import('./pages/StudentPlan.vue'),meta:{role:'student'} },
  { path:'/:pathMatch(.*)*',component:()=>import('./pages/NotFound.vue') },
] })
router.beforeEach(async to => {
  await ensureSession()
  const user=session.value?.user
  if (to.meta.role && !user) return {path:'/login/',query:{next:to.fullPath}}
  if (to.meta.role && user?.role!==to.meta.role) return user?.role==='coach'?'/coach/':'/student/'
  if (to.path==='/login/' && user) return user.role==='coach'?'/coach/':'/student/'
})
window.addEventListener('opencoach:login-required',()=>{void router.replace('/login/')})
export default router

import json
from ortools.sat.python import cp_model
from itertools import chain, combinations, product
import string
import random
from schedule_print import TT
import time

startTime = 0

teacher_counter = 0
room_counter = 0
group_counter = 0
instance_counter = 0
session_counter = 0

groups = {}
rooms = {}
teachers = {}
instances = {}
sessions = {}
constraints = []

room_claims = {}
pinned_sessions = {}
pinned_session_ids = []

sorted_list = []
satisfiability_tuples = []


names_used = set()

solver = cp_model.CpSolver()
solver.parameters.num_search_workers = 4
model = cp_model.CpModel()

# of slots per day
PERIODS_PER_DAY = None
# timetable repeats after # of weeks
REPEAT = None
# school days per week
WEEK_LEN = None
# recess after which period (index 0 so 3 means 4th period)
RECESS_AFTER = None

# Days Per cycle
CYCLE_LEN = None
# Total periods per cycle
TOTAL = None

MORN_TO_EVEN = None
ALL_SLOTS = None
START_BOD = None
START_BB = None
START_AB = None
START_EOD = None
START_TWO_IN_ROW = []
START_THREE_IN_ROW = []
START_FOUR_IN_ROW = []


def load():
    f = open('data.json',)
    data = json.load(f)
    f.close()
    init(data)

def init(data):
    global PERIODS_PER_DAY, REPEAT, WEEK_LEN, RECESS_AFTER, CYCLE_LEN, TOTAL, ALL_SLOTS, START_BOD, START_BB, START_AB, START_EOD, START_TWO_IN_ROW, START_THREE_IN_ROW, START_FOUR_IN_ROW, teachers, rooms, groups, instances, sessions, constraints, teacher_counter, room_counter, group_counter, instance_counter, session_counter, room_claims, pinned_sessions
    PERIODS_PER_DAY = data["PERIODS_PER_DAY"]
    REPEAT = data["REPEAT"]
    WEEK_LEN = data["WEEK_LEN"]
    RECESS_AFTER = data["RECESS_AFTER"]

    sessions = data["sessions"]
    instances = data["instances"]
    groups = data["groups"]
    rooms = data["rooms"]
    teachers = data["teachers"]
    constraints = data["constraints"]

    CYCLE_LEN = WEEK_LEN * REPEAT
    # Total periods per cycle
    TOTAL = PERIODS_PER_DAY * CYCLE_LEN

    MORN_TO_EVEN = [[i + j for i in range(0, TOTAL, PERIODS_PER_DAY)] for j in range(PERIODS_PER_DAY)]
    ALL_SLOTS = [i for i in range(TOTAL)]
    START_BOD = MORN_TO_EVEN[0]
    START_BB = MORN_TO_EVEN[RECESS_AFTER]
    START_AB = MORN_TO_EVEN[RECESS_AFTER + 1]
    START_EOD = MORN_TO_EVEN[PERIODS_PER_DAY - 1]
    START_TWO_IN_ROW = []
    START_THREE_IN_ROW = []
    START_FOUR_IN_ROW = []

    FIRST_CHAIN = (0, RECESS_AFTER + 1)
    SECOND_CHAIN = (RECESS_AFTER + 1, PERIODS_PER_DAY)

    for start, end in [FIRST_CHAIN, SECOND_CHAIN]:
        for i in range(start, end):
            if (i+2 <= end):
                START_TWO_IN_ROW.extend(MORN_TO_EVEN[i])
            if (i+3 <= end):
                START_THREE_IN_ROW.extend(MORN_TO_EVEN[i])
            if (i+4 <= end):
                START_FOUR_IN_ROW.extend(MORN_TO_EVEN[i])

    teacher_counter = len(teachers)
    room_counter = len(rooms)
    group_counter = len(groups)
    instance_counter = len(instances)
    session_counter = len(sessions)

    room_claims = {rid:[] for rid in range(room_counter)}
    pinned_sessions = {rid:[] for rid in range(room_counter)}

    print({
           "teachers": teacher_counter,
           "rooms": room_counter,
           "groups": group_counter,
           "instances": instance_counter,
           "sessions": session_counter
           })


def rndVar():
    name = str(random.choices(string.ascii_lowercase, k = 1)).join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k = 3))
    while (name in names_used):
        name = str(random.choices(string.ascii_lowercase, k = 1)).join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k = 3))
    names_used.add(name)
    return name

def reformat(data, key):
    obj = {}
    for k, v in data[key].items():
        obj[int(k)] = v
    return obj

def reorg():
    global session_counter, sessions
    for iid, iobj in instances.items():
        credits = iobj["periods_per_cycle"]
        elective_id = iid
        participating_groups = iobj["scope"]
        for tsr in iobj["teacher_subject_room"]:
            teacher_id = tsr[0]
            room_id = tsr[2]
            subject = tsr[1]

            sessions[session_counter] = {
                "credits" : credits,
                "elective_id" : elective_id,
                "participating_groups": participating_groups,
                "teacher_id": teacher_id,
                "room_id" : room_id,
                "subject" : subject
            }
            session_counter += 1

def dump(data):
    data["sessions"] = sessions
    data["sessions_counter"] = session_counter
    out_file = open("dump.json", "w")
    json.dump(data, out_file, indent = 4)
    out_file.close()

def allocate():
    print("Start: Allocating planning variables - for periods and room")
    for session_id, session_obj in sessions.items():
        periods = []
        for p in range(session_obj["credits"]):
            periods.append(model.NewIntVar(0, TOTAL-1, rndVar()))
        room = model.NewIntVar(0, room_counter-1, rndVar())
        session_obj["alloc_periods"] = periods
        session_obj["alloc_room_id"] = room
    print("Stop: Allocating planning variables - for periods and room")

# ----------------------------- Mandatory constraints (by definition) -------------------------------------------

def inSync():
    print("Start: Elective - All the different sessions are in sync")
    for elective_id in range(instance_counter):
        in_synch_sessions = []
        for session_id, session_obj in sessions.items():
            credits = session_obj["credits"]
            if session_obj["elective_id"] == elective_id:
                in_synch_sessions.append(session_id)

        all_pairs = list(combinations(in_synch_sessions, 2))
        for pair in all_pairs:
            #print("InSync sessions ", pair[0], pair[1])
            session_one_periods = sessions[pair[0]]["alloc_periods"]
            session_two_periods = sessions[pair[1]]["alloc_periods"]
            for p in range(len(session_one_periods)):
                model.Add(session_one_periods[p] == session_two_periods[p])
    print("Stop: Elective - All the different sessions are in sync")

def groupAddUp():
    print("Start: Group - All periods different")
    for gid in range(group_counter):
        group_periods = []
        electives_covered = []
        for session_id, session_obj in sessions.items():
            if (gid in session_obj["participating_groups"]) and (session_obj["elective_id"] not in electives_covered):
                group_periods += session_obj["alloc_periods"]
                electives_covered.append(session_obj["elective_id"])
        model.AddAllDifferent(group_periods)
    print("Stop: Group - All periods different")

def teacherNoConflict():
    print("Start: Teacher - No sessions with overlapping periods")
    for tid in range(teacher_counter):
        teacher_periods = []
        for session_id, session_obj in sessions.items():
            if session_obj["teacher_id"] == tid:
                teacher_periods += session_obj["alloc_periods"]
        model.AddAllDifferent(teacher_periods)
    print("Stop: Teacher - No sessions with overlapping periods")

def roomNoConflict():
    print("Start: Room - No Overlapping sessions")
    # Known rooms
    pre_allocated = {}
    for rid in range(room_counter):
        pers = []
        for session_id, session_obj in sessions.items():
            if session_obj["room_id"] == rid:
                pers.extend(session_obj["alloc_periods"])
        pers.extend(rooms[rid]['unavailability'])
        pers.extend(room_claims[rid])
        pers.extend(pinned_sessions[rid])
        pre_allocated[rid] = pers
        model.AddAllDifferent(pers)

    un_allocated_session_objs = []
    for session_id, session_obj in sessions.items():
        if (session_obj["room_id"] == -1) and (session_id not in pinned_session_ids):
            un_allocated_session_objs.append(session_obj)

    for session_obj_1 in un_allocated_session_objs:
        for session_obj_2 in un_allocated_session_objs:
            if session_obj_1 != session_obj_2:
                b = model.NewBoolVar(rndVar())
                model.Add(session_obj_1["alloc_room_id"] == session_obj_2["alloc_room_id"]).OnlyEnforceIf(b)
                model.Add(session_obj_1["alloc_room_id"] != session_obj_2["alloc_room_id"]).OnlyEnforceIf(b.Not())

                for p1 in session_obj_1["alloc_periods"]:
                    for p2 in session_obj_2["alloc_periods"]:
                        model.Add(p1 != p2).OnlyEnforceIf(b)

    for session_obj in un_allocated_session_objs:
        # for room_id in range(room_counter)
        for room_id in range(room_counter):
            c = model.NewBoolVar(rndVar())
            model.Add(session_obj["alloc_room_id"] == room_id).OnlyEnforceIf(c)
            model.Add(session_obj["alloc_room_id"] != room_id).OnlyEnforceIf(c.Not())

            for p in session_obj["alloc_periods"]:
                for alc in pre_allocated[room_id]:
                    model.Add(p != alc).OnlyEnforceIf(c)

    print("Stop: Room - No Overlapping sessions")


def rommPreFill():
    print("Start: Room assignment - Populate room variables wherever known")
    for session_id, session_obj in sessions.items():
        if session_obj["room_id"] != -1:
            model.Add(session_obj["alloc_room_id"] == session_obj["room_id"])
    print("Stop: Room assignment - Populate room variables wherever known")


# ----------------------------- Mandatory constraints (by definition) -------------------------------------------

def isAllClassTeacherFirstPeriod():
    print("Start: Class teacher first period")
    ic = [] # array of booleans representing individual compliance
    for gid, gobj in groups.items():
        classteacher_id = gobj["classteacher"]
        ic.append(isClassTeacherFirstPeriod(classteacher_id, gid))

    b = model.NewBoolVar(rndVar())
    model.Add(sum(ic) == len(ic)).OnlyEnforceIf(b)
    model.Add(sum(ic) != len(ic)).OnlyEnforceIf(b.Not())
    print("Stop: Class teacher first period")
    return b

def isClassTeacherFirstPeriod(classteacher_id, group_id):
    #print("Start: Class teacher first period ", classteacher_id, group_id)
    classteacher_periods = []
    for session_id, session_obj in sessions.items():
        if (((len(session_obj['participating_groups']) == 1) and (group_id in session_obj['participating_groups'])) and (session_obj["teacher_id"] == classteacher_id)):
        #if (session_obj["teacher_id"] == classteacher_id) and ([group_id] == session_obj["participating_groups"]):
            classteacher_periods += session_obj["alloc_periods"]
    fp = [] # array of booleans whether a given period is firstPeriod
    for period in classteacher_periods:
        fp.append(isFirstPeriod(period))

    b = model.NewBoolVar(rndVar()) # individual compliance
    model.Add(sum(fp) == CYCLE_LEN).OnlyEnforceIf(b)
    model.Add(sum(fp) != CYCLE_LEN).OnlyEnforceIf(b.Not())
    #print("Stop: Class teacher first period")
    return b


def isAllClassTeacherEveryDay():
    print("Start: Class teacher every day")
    ic = [] # array of booleans representing individual compliance
    for gid, gobj in groups.items():
        classteacher_id = gobj["classteacher"]
        ic.append(isClassTeacherEveryDay(classteacher_id, gid))

    b = model.NewBoolVar(rndVar())
    model.Add(sum(ic) == len(ic)).OnlyEnforceIf(b)
    model.Add(sum(ic) != len(ic)).OnlyEnforceIf(b.Not())
    print("Stop: Class teacher every day")
    return b

def isClassTeacherEveryDay(classteacher_id, group_id):
    #print("Start: Class teacher every day ", classteacher_id, group_id)
    classteacher_periods = []

    for session_id, session_obj in sessions.items():
#        if session_obj["teacher_id"] == classteacher_id:
        if (((len(session_obj['participating_groups']) == 1) and (group_id in session_obj['participating_groups'])) and (session_obj["teacher_id"] == classteacher_id)):
            classteacher_periods += session_obj["alloc_periods"]

    increasing(classteacher_periods)

    # reprents boolean saying whether teaacher has at least on period on corresponding day
    dn = [model.NewBoolVar(rndVar()) for day in range(CYCLE_LEN)]

    for day in range(CYCLE_LEN):
        pod = [] # array of booleans whether a period is on a day
        for period in classteacher_periods:
            pod.append(isOnDay(period, day))

        model.Add(sum(pod) >= 1).OnlyEnforceIf(dn[day])
        model.Add(sum(pod) < 1).OnlyEnforceIf(dn[day].Not())

    b = model.NewBoolVar(rndVar()) # individual compliance

    dnp = [dn[day].Not() for day in range(CYCLE_LEN)]
    model.AddBoolAnd(dn).OnlyEnforceIf(b)
    model.AddBoolOr(dnp).OnlyEnforceIf(b.Not())
    #print("Stop: Class teacher every day ")
    return b

def isRoomUnavailability(room_id, unavailability_list):
    # Feasible only if session doesn't use room or if uses the room it doesn't use it in the unavailable times
    # Validity condition
    print("Start: Room unavailability", room_id, unavailability_list)
    b = model.NewBoolVar(rndVar())
    session_compatible = [model.NewBoolVar(rndVar()) for i in range(len(sessions))]
    count = 0
    for session_id, session_obj in sessions.items():

        session_no_timings_conflict = model.NewBoolVar(rndVar())

        session_happens_in_room = model.NewBoolVar(rndVar())
        model.Add(session_obj["alloc_room_id"] == room_id).OnlyEnforceIf(session_happens_in_room)
        model.Add(session_obj["alloc_room_id"] != room_id).OnlyEnforceIf(session_happens_in_room.Not())

        # Now we have to enforce that none of the session slots lines up with the unavailability PERIODS

        possibilities = list(product(session_obj["alloc_periods"], unavailability_list))
        n = len(possibilities)
        a = [model.NewBoolVar(rndVar()) for i in range(n)]

        for i in range(n):
            model.Add(possibilities[i][0] != possibilities[i][1]).OnlyEnforceIf(a[i])
            model.Add(possibilities[i][0] == possibilities[i][1]).OnlyEnforceIf(a[i].Not())

        ap = [a[i].Not() for i in range(n)]

        model.AddBoolAnd(a).OnlyEnforceIf(session_no_timings_conflict)
        model.AddBoolOr(ap).OnlyEnforceIf(session_no_timings_conflict.Not())

        model.AddBoolOr([session_happens_in_room.Not(), session_no_timings_conflict]).OnlyEnforceIf(session_compatible[count])
        model.AddBoolAnd([session_happens_in_room, session_no_timings_conflict.Not()]).OnlyEnforceIf(session_compatible[count].Not())
        count += 1

    # Complement
    session_incompatible = [session_compatible[i].Not() for i in range(len(session_compatible))]
    model.AddBoolAnd(session_compatible).OnlyEnforceIf(b)
    model.AddBoolOr(session_incompatible).OnlyEnforceIf(b.Not())
    print("Stop: Room unavailability")
    return b



def isTeacherUnavailability(teacher_id, unavailability_list):
    print("Start: Teacher unavailability", teacher_id, unavailability_list)
    teacher_periods = []
    for session_id, session_obj in sessions.items():
        if session_obj["teacher_id"] == teacher_id:
            teacher_periods.extend(session_obj["alloc_periods"])

    possibilities = list(product(teacher_periods, unavailability_list))
    n = len(possibilities)
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for i in range(n)]

    for i in range(n):
        model.Add(possibilities[i][0] != possibilities[i][1]).OnlyEnforceIf(a[i])
        model.Add(possibilities[i][0] == possibilities[i][1]).OnlyEnforceIf(a[i].Not())

    ap = [a[i].Not() for i in range(n)]

    model.AddBoolAnd(a).OnlyEnforceIf(b)
    model.AddBoolOr(ap).OnlyEnforceIf(b.Not())
    print("Stop: Teacher unavailability")
    return b


def isTeacherNotLikeRooms(teacher_id, rooms_list):
    print("Stop: Teacher room inaccessibility", teacher_id, rooms_list)
    cumulative_session_rooms_list = []
    for session_id, session_obj in sessions.items():
        if session_obj["teacher_id"] == teacher_id:
            cumulative_session_rooms_list.append(session_obj["alloc_room_id"])

    possibilities = list(product(cumulative_session_rooms_list, rooms_list))
    n = len(possibilities)
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for i in range(n)]

    for i in range(n):
        model.Add(possibilities[i][0] != possibilities[i][1]).OnlyEnforceIf(a[i])
        model.Add(possibilities[i][0] == possibilities[i][1]).OnlyEnforceIf(a[i].Not())

    ap = [a[i].Not() for i in range(n)]

    model.AddBoolAnd(a).OnlyEnforceIf(b)
    model.AddBoolOr(ap).OnlyEnforceIf(b.Not())
    print("Stop: Teacher room accessibility")
    return b

def isTeacherLikeRooms(teacher_id, rooms_list):
    return isTeacherNotLikeRooms(teacher_id, rooms_list).Not()

def getLectureRooms():
    lecture_rooms = []
    for rid in range(room_counter):
        if rooms[rid]["type"] == 100:
            lecture_rooms.append(rid)

    return lecture_rooms



def isRoomsWhitelistedForSession(sid, whitelist):
    print("Start: Rooms whitelisted for session", sid, whitelist)
    n = len(whitelist)
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for i in range(n)]
    for session_id, session_obj in sessions.items():
        if session_id == sid:
            session_room = session_obj["alloc_room_id"]
            for i in range(n):
                model.Add(session_room == whitelist[i]).OnlyEnforceIf(a[i])
                model.Add(session_room != whitelist[i]).OnlyEnforceIf(a[i].Not())

    ap = [a[i].Not() for i in range(n)]

    model.AddBoolOr(a).OnlyEnforceIf(b)
    model.AddBoolAnd(ap).OnlyEnforceIf(b.Not())
    print("Stop: Rooms whitelisted for session")
    return b

def isRoomsBlacklistedForSession(sid, blacklist):
    print("Start: Rooms blacklisted for session", sid, blacklist)
    n = len(blacklist)
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for i in range(n)]
    for session_id, session_obj in sessions.items():
        if session_id == sid:
            session_room = session_obj["alloc_room_id"]
            for i in range(n):
                model.Add(session_room != blacklist[i]).OnlyEnforceIf(a[i])
                model.Add(session_room == blacklist[i]).OnlyEnforceIf(a[i].Not())

    ap = [a[i].Not() for i in range(n)]

    model.AddBoolAnd(a).OnlyEnforceIf(b)
    model.AddBoolOr(ap).OnlyEnforceIf(b.Not())
    print("Stop: Rooms blacklisted for session")
    return b

def  isRoomsNotBlacklistedForSession(sid, blacklist):
    return  isRoomsBlacklistedForSession(sid, blacklist).Not()

def  isRoomsNotBlacklistedForSessions(sids, blacklist):
    return  isRoomsBlacklistedForSession(sids, blacklist).Not()

def isRoomsBlacklistedForSessions(sids, blacklist):
    ic = [] # array of booleans representing individual compliance
    for sid in sids:
        ic.append(isRoomsBlacklistedForSession(sid, blacklist))

    b = model.NewBoolVar(rndVar())
    model.Add(sum(ic) == len(ic)).OnlyEnforceIf(b)
    model.Add(sum(ic) != len(ic)).OnlyEnforceIf(b.Not())
    return b

def isRoomToBeAvoidedForSession(sid, rid):
    return isPinSessionToRoom(sid, rid).Not()



def isLimitSessionsToLectureRooms(sids):
    print("Start: Limit to Lecture rooms", sids)
    b = model.NewBoolVar(rndVar())
    conditions = []
    for sid in sids:
        conditions.append(isRoomsWhitelistedForSession(sid, getLectureRooms()))
    conditions_complement = [conditions[i].Not() for i in range(len(conditions))]
    model.AddBoolAnd(conditions).OnlyEnforceIf(b)
    model.AddBoolOr(conditions_complement).OnlyEnforceIf(b.Not())
    print("Stop: Limit to Lecture rooms")
    return b


def isPinSessionToRoom(sid, rid):
    print("Start: Pin session to room", sid, rid)
    b = model.NewBoolVar(rndVar())
    for session_id, session_obj in sessions.items():
        if session_id == sid:
            session_room = session_obj["alloc_room_id"]
            model.Add(session_room == rid).OnlyEnforceIf(b)
            model.Add(session_room != rid).OnlyEnforceIf(b.Not())
    print("Stop: Pin session to room")
    return b

def isOnSameHalf(var1, var2):
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for half in range(2*CYCLE_LEN)]
    for half in range(2*CYCLE_LEN):
        r1 = isOnHalf(var1, half)
        r2 = isOnHalf(var2, half)

        model.AddBoolAnd([r1, r2]).OnlyEnforceIf(a[half])
        model.AddBoolOr([r1.Not(), r2.Not()]).OnlyEnforceIf(a[half].Not())
    ap = [a[half].Not() for half in range(2*CYCLE_LEN)]
    model.AddBoolOr(a).OnlyEnforceIf(b)
    model.AddBoolAnd(ap).OnlyEnforceIf(b.Not())
    return b

def isNotOnSameHalf(var1, var2):
    return isOnSameHalf(var1, var2).Not()

def isOnSameDay(var1, var2):
    b = model.NewBoolVar(rndVar())
    a = [model.NewBoolVar(rndVar()) for day in range(CYCLE_LEN)]
    for day in range(CYCLE_LEN):
        r1 = isOnDay(var1, day)
        r2 = isOnDay(var2, day)

        model.AddBoolAnd([r1, r2]).OnlyEnforceIf(a[day])
        model.AddBoolOr([r1.Not(), r2.Not()]).OnlyEnforceIf(a[day].Not())
    ap = [a[day].Not() for day in range(CYCLE_LEN)]
    model.AddBoolOr(a).OnlyEnforceIf(b)
    model.AddBoolAnd(ap).OnlyEnforceIf(b.Not())
    return b

def isNotOnSameDay(var1, var2):
    return isOnSameDay(var1, var2).Not()



def isFirstHalf(var):
    global teachers, groups, rooms, instances, TOTAL, instance_counter, group_counter, room_counter, teacher_counter, model
    b = model.NewBoolVar(rndVar())
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(FIRST_HALF), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(SECOND_HALF), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isSecondtHalf(var):
    global teachers, groups, rooms, instances, TOTAL, instance_counter, group_counter, room_counter, teacher_counter, model
    b = model.NewBoolVar(rndVar())
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(SECOND_HALF), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(FIRST_HALF), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b


def isJustBeforeLunch(var):
    global teachers, groups, rooms, instances, TOTAL, instance_counter, group_counter, room_counter, teacher_counter, model
    b = model.NewBoolVar(rndVar())
    NOT_START_BB = list(set(ALL_SLOTS) - set(START_BB))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_BB), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(NOT_START_BB), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isNotJustBeforeLunch(var):
    return isJustBeforeLunch(var).Not()

def isJustAfterLunch(var):
    global teachers, groups, rooms, instances, TOTAL, instance_counter, group_counter, room_counter, teacher_counter, model
    b = model.NewBoolVar(rndVar())
    NOT_START_AB = list(set(ALL_SLOTS) - set(START_AB))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_AB), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(NOT_START_AB), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isNotJustAfterLunch(var):
    return isJustAfterLunch(var).Not()


def isFirstPeriod(var):
    b = model.NewBoolVar(rndVar())
    NOT_START_BOD = list(set(ALL_SLOTS) - set(START_BOD))

    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_BOD), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(NOT_START_BOD), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b


def isNotFirstPeriod(var):
    return isFirstPeriod(var).Not()



def isLastPeriod(var):
    b = model.NewBoolVar(rndVar())
    NOT_START_EOD = list(set(ALL_SLOTS) - set(START_EOD))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_EOD), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(NOT_START_EOD), rndVar())

    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isNotLastPeriod(var):
    return isLastPeriod(var).Not()

    # Start of week is 0 (typically Monday)
def isOnDay(var, DAY):
    day_membership = []
    day_non_membership = []
    for i in range(TOTAL):
        if i // PERIODS_PER_DAY == DAY:
            day_membership.append(i)
        else:
            day_non_membership.append(i)
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(day_membership), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(day_non_membership), rndVar())

    b = model.NewBoolVar(rndVar())
    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isOnHalf(var, HALF):
    half_membership = []
    half_non_membership = []
    DAY = HALF // 2
    FIRST = True if (HALF % 2 == 0) else False
    for i in range(TOTAL):
        if ((i // PERIODS_PER_DAY) == DAY) and ((((i % PERIODS_PER_DAY) <= RECESS_AFTER) and FIRST) or (((i % PERIODS_PER_DAY) > RECESS_AFTER) and (not FIRST))):
            half_membership.append(i)
        else:
            half_non_membership.append(i)
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(half_membership), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(half_non_membership), rndVar())

    b = model.NewBoolVar(rndVar())
    model.Add(inside == var).OnlyEnforceIf(b)
    model.Add(outside == var).OnlyEnforceIf(b.Not())
    return b

def isNotOnDay(var, DAY):
    return isOnDay(var, DAY).Not()

def increasing(vars):
    n = len(vars)
    for i in range(0, n - 1):
        model.Add(vars[i] <= vars[i + 1])



def isConsecutivePeriod2(var1, var2):

    a = model.NewBoolVar(rndVar())
    b = model.NewBoolVar(rndVar())
    c = model.NewBoolVar(rndVar())
    model.Add(var2 == var1 + 1).OnlyEnforceIf(a)
    model.Add(var2 != var1 + 1).OnlyEnforceIf(a.Not())
    # var1 is not the last period or period before RECESS_AFTER
    REST_INTERVAL = list(set(ALL_SLOTS) - set(START_TWO_IN_ROW))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_TWO_IN_ROW), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(REST_INTERVAL), rndVar())

    model.Add(inside == var1).OnlyEnforceIf(b)
    model.Add(outside == var1).OnlyEnforceIf(b.Not())

    model.AddBoolAnd([a, b]).OnlyEnforceIf(c)
    model.AddBoolOr([a.Not(), b.Not()]).OnlyEnforceIf(c.Not())
    return c

def isConsecutivePeriod3(var1, var2, var3):

    a = model.NewBoolVar(rndVar())
    model.Add(var2 == var1 + 1).OnlyEnforceIf(a)
    model.Add(var2 != var1 + 1).OnlyEnforceIf(a.Not())
    b = model.NewBoolVar(rndVar())
    model.Add(var3 == var2 + 1).OnlyEnforceIf(b)
    model.Add(var3 != var2 + 1).OnlyEnforceIf(b.Not())
    c = model.NewBoolVar(rndVar())
    REST_INTERVAL = list(set(ALL_SLOTS) - set(START_THREE_IN_ROW))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_THREE_IN_ROW), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(REST_INTERVAL), rndVar())

    model.Add(inside == var1).OnlyEnforceIf(c)
    model.Add(outside == var1).OnlyEnforceIf(c.Not())
    d = model.NewBoolVar(rndVar())

    model.AddBoolAnd([a, b, c]).OnlyEnforceIf(d)
    model.AddBoolOr([a.Not(), b.Not(), c.Not()]).OnlyEnforceIf(d.Not())
    return d

def isConsecutivePeriod4(var1, var2, var3, var4):

    a = model.NewBoolVar(rndVar())
    model.Add(var2 == var1 + 1).OnlyEnforceIf(a)
    model.Add(var2 != var1 + 1).OnlyEnforceIf(a.Not())
    b = model.NewBoolVar(rndVar())
    model.Add(var3 == var2 + 1).OnlyEnforceIf(b)
    model.Add(var3 != var2 + 1).OnlyEnforceIf(b.Not())
    c = model.NewBoolVar(rndVar())
    model.Add(var4 == var3 + 1).OnlyEnforceIf(c)
    model.Add(var4 != var3 + 1).OnlyEnforceIf(c.Not())
    d = model.NewBoolVar(rndVar())
    REST_INTERVAL = list(set(ALL_SLOTS) - set(START_FOUR_IN_ROW))
    inside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(START_FOUR_IN_ROW), rndVar())
    outside = model.NewIntVarFromDomain(cp_model.Domain.FromValues(REST_INTERVAL), rndVar())

    model.Add(inside == var1).OnlyEnforceIf(d)
    model.Add(outside == var1).OnlyEnforceIf(d.Not())
    #print([tuple([i]) for i in START_FOUR_IN_ROW])
    e = model.NewBoolVar(rndVar())
    model.AddBoolAnd([a, b, c, d]).OnlyEnforceIf(e)
    model.AddBoolOr([a.Not(), b.Not(), c.Not(), d.Not()]).OnlyEnforceIf(e.Not())

    return e

def isConsecutivePeriods(vars):
    n = len(vars)
    if n == 2:
        return isConsecutivePeriod2(vars[0], vars[1])
    if n == 3:
        return isConsecutivePeriod3(vars[0], vars[1], vars[2])
    if n == 4:
        return isConsecutivePeriod4(vars[0], vars[1], vars[2], vars[3])

    return False

def isNotConsecutivePeriods(vars):
    return isConsecutivePeriods(vars).Not()

def isDifferentDays(vars):
    all_pairs = list(combinations(vars, 2))
    clauses = []
    for pair in all_pairs:
        clauses.append(isNotOnSameDay(pair[0], pair[1]))

    b = model.NewBoolVar(rndVar())
    clauses_prime = [clauses[i].Not() for i in range(len(clauses))]
    model.AddBoolAnd(clauses).OnlyEnforceIf(b)
    model.AddBoolOr(clauses_prime).OnlyEnforceIf(b.Not())
    return b

def isDifferentHalves(vars):
    all_pairs = list(combinations(vars, 2))
    clauses = []
    for pair in all_pairs:
        clauses.append(isNotOnSameHalf(pair[0], pair[1]))

    b = model.NewBoolVar(rndVar())
    clauses_prime = [clauses[i].Not() for i in range(len(clauses))]
    model.AddBoolAnd(clauses).OnlyEnforceIf(b)
    model.AddBoolOr(clauses_prime).OnlyEnforceIf(b.Not())
    return b


# ------------------------------------ Helper Functions -------------------------------------------------
def fetchClassCalendar(gid):

    vars = {}
    iids_covered = []
    for session_id, session_obj in sessions.items():
        if (gid in session_obj["participating_groups"]):
            content = ""
            for tsr in instances[session_obj["elective_id"]]["teacher_subject_room"]:
                content += teachers[tsr[0]]['name'] + ":" + tsr[1] + ":" + rooms[solver.Value(session_obj["alloc_room_id"])]["name"]
            for i in range(session_obj["credits"]):
                vars[solver.Value(session_obj["alloc_periods"][i])] = {"teachers_subjects_rooms" : content}
    return vars

def fetchTeacherCalendar(teacher_id):
    vars = {}
    for session_id, session_obj in sessions.items():
        if (session_obj["teacher_id"] == teacher_id):
            for i in range(session_obj["credits"]):
                vars[solver.Value(session_obj["alloc_periods"][i])] = {
                                                                       "session_id" : session_id,
                                                                       "teacher" : teachers[session_obj["teacher_id"]]["name"],
                                                                       "subject" : session_obj["subject"],
                                                                       "room" : rooms[solver.Value(session_obj["alloc_room_id"])]["name"],
                                                                       "classes" : [groups[gid]["name"] for gid in session_obj["participating_groups"]]
                                                                       }
    return vars

def fetchRoomCalendar(room_id):
    vars = {}
    for session_id, session_obj in sessions.items():
        if (solver.Value(session_obj["alloc_room_id"]) == room_id):
            for i in range(session_obj["credits"]):
                vars[solver.Value(session_obj["alloc_periods"][i])] = {
                                                                       "session_id" : session_id,
                                                                       "teacher" : teachers[session_obj["teacher_id"]]["name"],
                                                                       "subject" : session_obj["subject"],
                                                                       "room" : rooms[solver.Value(session_obj["alloc_room_id"])]["name"],
                                                                       "classes" : [groups[gid]["name"] for gid in session_obj["participating_groups"]]
                                                                       }
    return vars

def printArr(vars):
    for i in range(PERIODS_PER_DAY):
        schedule = ""
        for j in range(CYCLE_LEN):
            print (vars[((j*PERIODS_PER_DAY) + i)])
        print("\n")

def saveSolution():

    print("Saving solution ...")

    tt = TT(PERIODS_PER_DAY, WEEK_LEN, REPEAT, RECESS_AFTER, "G")
    print("Creating groups spreadsheet ...")
    for gid in range(group_counter):
        print("Adding sheet for group ...", gid)
        vals = fetchClassCalendar(gid)
        dt = []
        for val in [vals.get(i, "") for i in range(TOTAL)]:
            if val == "":
                dt.append(val)
            else:
                dt.append(val['teachers_subjects_rooms'])

        tt.fill(gid, dt)
    tt.saveNClose()
    print("Created groups spreadsheet ...")

    tt1 = TT(PERIODS_PER_DAY, WEEK_LEN, REPEAT, RECESS_AFTER, "R")

    print("Creating rooms spreadsheet ...")
    for rid in range(room_counter):
        print("Adding sheet for room ...", rid)
        vals = fetchRoomCalendar(rid)
        dt = []
        for val in [vals.get(i, "") for i in range(TOTAL)]:
            if val == "":
                dt.append(val)
            else:
                dt.append(str(val['classes']) + '\n' + val['teacher'])

        tt1.fill(rid, dt)
    tt1.saveNClose()
    print("Created rooms spreadsheet ...")

    tt2 = TT(PERIODS_PER_DAY, WEEK_LEN, REPEAT, RECESS_AFTER, "T")
    print("Creating teachers spreadsheet ...")
    for tid in range(teacher_counter):
        print("Adding sheet for teacher ...", tid)
        vals = fetchTeacherCalendar(tid)
        dt = []
        for val in [vals.get(i, "") for i in range(TOTAL)]:
            if val == "":
                dt.append(val)
            else:
                dt.append(val['room'] + '\n' + val['subject'] + '\n' + str(val['classes']))

        tt2.fill(tid, dt)
    tt2.saveNClose()
    print("Created teachers spreadsheet ...")



def printSessions():
    print("Printing Sessions ...")
    for session_id, session_obj in sessions.items():
        print(session_id, session_obj["elective_id"], teachers[session_obj["teacher_id"]]["name"] + ":" + session_obj["subject"])
        print("Room ", solver.Value(session_obj["alloc_room_id"]) )
        print("Periods ", [solver.Value(session_obj['alloc_periods'][i]) for i in range(len(session_obj['alloc_periods']))] )

def analysis():
    for rid in range(room_counter):
        print("Room load ...", rid)
        for session_id, session_obj in sessions.items():
            if solver.Value(session_obj["alloc_room_id"]) == rid:
                print([solver.Value(session_obj['alloc_periods'][i]) for i in range(len(session_obj['alloc_periods']))], "                 ", session_id, session_obj["elective_id"], teachers[session_obj["teacher_id"]]["name"] + ":" + session_obj["subject"])



#        print(session_id, session_obj["elective_id"], teachers[session_obj["teacher_id"]]["name"] + ":" + session_obj["subject"] + ":" + solver.Value(session_obj["alloc_room_id"]), session_obj["participating_groups"], len(session_obj["alloc_periods"]), [solver.Value(session_obj["alloc_periods"][i]) for i in range(len(session_obj["alloc_periods"]))])
# ------------------------------------ Helper Functions -------------------------------------------------


def postObjective():
    print("Post objective ...")
    model.Maximize(sum(satisfiability_tuples[i][0] * satisfiability_tuples[i][1]  for i in range(len(satisfiability_tuples))))
    print("Posted objective ...")

def postConstraints(constraints):
    global pinned_session_ids, pinned_sessions, room_claims
    print("Posting constraints ...")
    for constraint in constraints:
        is_ignore = constraint["JSON_KEY_IS_IGNORE"]
        if is_ignore:
            continue;

        is_hard = constraint["JSON_KEY_IS_HARD"]

        if constraint["JSON_KEY_TYPE"] == "CLASSTEACHER_FIRST_PERIOD":
            print("Classteacher First Period Constraint")
            result = isAllClassTeacherFirstPeriod()
            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))
        elif constraint["JSON_KEY_TYPE"] == "CLASSTEACHER_PERIOD_A_DAY":
            print("Classteacher Period a day Constraint")
            result = isAllClassTeacherEveryDay()
            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))

        elif constraint["JSON_KEY_TYPE"] == "ROOM_CLAIM":
            print("Room Claim constraint")
            session_id = constraint["JSON_KEY_SESSION_ID"]
            period_pos = constraint["JSON_KEY_PERIOD_POS"]
            room_id = constraint["JSON_KEY_ROOM_ID"]
            periods = [sessions[session_id]["alloc_periods"][p] for p in period_pos]
            if session_id not in sorted_list:
                increasing(sessions[session_id]["alloc_periods"])
                sorted_list.append(session_id)

            room_claims[room_id] = room_claims[room_id] + periods

        elif constraint["JSON_KEY_TYPE"] == "SESSION_INTERDEPENDENCE":
            print("Session interdependence Constraint")
            session_id = constraint["JSON_KEY_SESSION_ID"]
            period_pos = constraint["JSON_KEY_PERIOD_POS"]
            condition = constraint["JSON_KEY_CONDITION"]
            periods = [sessions[session_id]["alloc_periods"][p] for p in period_pos]
            if session_id not in sorted_list:
                increasing(sessions[session_id]["alloc_periods"])
                sorted_list.append(session_id)

            if (condition == "IS_AC"):
                result = isConsecutivePeriods(periods)
                if is_hard:
                    model.Add(result == True)
                else:
                    importance = constraint["JSON_KEY_IMPORTANCE"]
                    satisfiability_tuples.append((result, importance))

            elif (condition == "IS_DD"):
                result = isDifferentDays(periods)
                if is_hard:
                    model.Add(result == True)
                else:
                    importance = constraint["JSON_KEY_IMPORTANCE"]
                    satisfiability_tuples.append((result, importance))

            elif (condition == "IS_DH"):
                result = isDifferentHalves(periods)
                if is_hard:
                    model.Add(result == True)
                else:
                    importance = constraint["JSON_KEY_IMPORTANCE"]
                    satisfiability_tuples.append((result, importance))


        elif constraint["JSON_KEY_TYPE"] == "SESSION_DAYS":
            print("Session Days Constraint")
            session_id = constraint["JSON_KEY_SESSION_ID"]
            period_pos = constraint["JSON_KEY_PERIOD_POS"]
            qualifier = constraint["JSON_KEY_QUALIFIER"]
            day = constraint["JSON_KEY_CONDITION"]
            periods = [sessions[session_id]["alloc_periods"][p] for p in period_pos]
            if session_id not in sorted_list:
                increasing(sessions[session_id]["alloc_periods"])
                sorted_list.append(session_id)

            clauses = []
            for period in periods:
                clauses.append(isOnDay(period, day))

            final = model.NewBoolVar(rndVar())
            if qualifier == "ALL":
                model.Add(sum(clauses) == len(clauses)).OnlyEnforceIf(final)
                model.Add(sum(clauses) != len(clauses)).OnlyEnforceIf(final.Not())
            elif qualifier == "AT_MOST":
                model.Add(sum(clauses) <= 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) >  1).OnlyEnforceIf(final.Not())
            elif qualifier == "AT_LEAST":
                model.Add(sum(clauses) >= 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) <  1).OnlyEnforceIf(final.Not())
            elif qualifier == "EXACTLY":
                model.Add(sum(clauses) == 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) != 1).OnlyEnforceIf(final.Not())
            else:
                model.Add(sum(clauses) == 0).OnlyEnforceIf(final)
                model.Add(sum(clauses) != 0).OnlyEnforceIf(final.Not())

            if is_hard:
                model.Add(final == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((final, importance))
        elif constraint["JSON_KEY_TYPE"] == "SESSION_TIMINGS":
            print("Session Timings Constraint")
            session_id = constraint["JSON_KEY_SESSION_ID"]
            period_pos = constraint["JSON_KEY_PERIOD_POS"]
            qualifier = constraint["JSON_KEY_QUALIFIER"]
            condition = constraint["JSON_KEY_CONDITION"]
            periods = [sessions[session_id]["alloc_periods"][p] for p in period_pos]
            if session_id not in sorted_list:
                increasing(sessions[session_id]["alloc_periods"])
                sorted_list.append(session_id)
            clauses = []
            for period in periods:
                if (condition == "IS_FP"):
                    clauses.append(isFirstPeriod(period))
                if (condition == "IS_LP"):
                    clauses.append(isLastPeriod(period))
                if (condition == "IS_JBL"):
                    clauses.append(isJustBeforeLunch(period))
                if (condition == "IS_JAL"):
                    clauses.append(isJustAfterLunch(period))
                if (condition == "IS_ON_DAY"):
                    clauses.append(isOnDay(period, DAY))
                if (condition == "IS_IN_FHALF"):
                    clauses.append(isFirstHalf(period))
                if (condition == "IS_IN_SHALF"):
                    clauses.append(isSecondtHalf(period))
            final = model.NewBoolVar(rndVar())
            if qualifier == "ALL":
                model.Add(sum(clauses) == len(clauses)).OnlyEnforceIf(final)
                model.Add(sum(clauses) != len(clauses)).OnlyEnforceIf(final.Not())
            elif qualifier == "AT_MOST":
                model.Add(sum(clauses) <= 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) >  1).OnlyEnforceIf(final.Not())
            elif qualifier == "AT_LEAST":
                model.Add(sum(clauses) >= 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) <  1).OnlyEnforceIf(final.Not())
            elif qualifier == "EXACTLY":
                model.Add(sum(clauses) == 1).OnlyEnforceIf(final)
                model.Add(sum(clauses) != 1).OnlyEnforceIf(final.Not())
            else:
                model.Add(sum(clauses) == 0).OnlyEnforceIf(final)
                model.Add(sum(clauses) != 0).OnlyEnforceIf(final.Not())

            if is_hard:
                model.Add(final == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((final, importance))


        elif constraint["JSON_KEY_TYPE"] == "TEACHER_AVAILABILITY":
            print("Teacher availability constraint")
            teacher_id = constraint["JSON_KEY_TEACHER_ID"]
            availability = constraint["JSON_KEY_AVAILABILITY"]
            result = isTeacherUnavailability(teacher_id, availability)
            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))

        elif constraint["JSON_KEY_TYPE"] == "ROOM_AVAILABILITY":
            print("Room availability constraint ")
            room_id = constraint["JSON_KEY_ROOM_ID"]
            availability = constraint["JSON_KEY_AVAILABILITY"]

            result = isRoomUnavailability(room_id, availability)
            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))

        elif constraint["JSON_KEY_TYPE"] == "TEACHER_ACCESSIBILITY":
            print("Teacher Accessibility Constraint")
            is_accessible = constraint["JSON_KEY_IS_ACCESSIBLE"]
            teacher_id = constraint["JSON_KEY_TEACHER_ID"]
            room_ids = constraint["JSON_KEY_ROOM_IDS"]
            result = None
            if is_accessible:
                result = isTeacherNotLikeRooms(teacher_id, room_ids)
            else:
                result = isTeacherLikeRooms(teacher_id, room_ids)

            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))

        elif constraint["JSON_KEY_TYPE"] == "ROOM_SUITABILITY":
            print("Room suitability Constraint")
            session_ids = constraint["JSON_KEY_SESSION_IDS"]
            is_suitable = constraint["JSON_KEY_IS_SUITED"]
            room_ids = constraint["JSON_KEY_ROOM_IDS"]
            result = None
            if is_suitable:
                result = isRoomsNotBlacklistedForSessions(session_ids, room_ids)
            else:
                result = isRoomsBlacklistedForSessions(session_ids, room_ids)

            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))

        elif constraint["JSON_KEY_TYPE"] == "LECTURE_ONLY":
            print("Lecture Only Constraint")
            session_ids = constraint["JSON_KEY_SESSION_IDS"]
            result = isLimitSessionsToLectureRooms(session_ids)
            if is_hard:
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))
        elif constraint["JSON_KEY_TYPE"] == "PIN_SESSION":
            print("PIN Session Constraint")
            session_id = constraint["JSON_KEY_SESSION_ID"]
            room_id = constraint["JSON_KEY_ROOM_ID"]
            result = isPinSessionToRoom(session_id, room_id)
            if is_hard:
                pinned_sessions[room_id].extend(sessions[session_id]['alloc_periods'])
                pinned_session_ids.append(session_id)
                model.Add(result == True)
            else:
                importance = constraint["JSON_KEY_IMPORTANCE"]
                satisfiability_tuples.append((result, importance))
        else:
            print("Unhandled Constraint", constraint["JSON_KEY_TYPE"])

    print("Posted Constraints")


def solve():
    status = solver.Solve(model)
    statusName = solver.StatusName(status)

    print()
    print('Statistics')
    print('  - conflicts       : %i' % solver.NumConflicts())
    print('  - objective value : %i' % solver.ObjectiveValue())
    print('  - branches        : %i' % solver.NumBranches())
    print('  - wall time       : %f s' % solver.WallTime())
    print('  - status', statusName)
    print(solver.ObjectiveValue())

    print('Status #' + statusName + "#")
    if (statusName == 'INFEASIBLE'):
        exit()

    saveSolution()
    if (statusName == 'OPTIMAL'):
        analysis()

    elapsesdTime = time.time() - startTime
    hours = int(elapsesdTime/3600)
    minutes = int((elapsesdTime - hours*3600)/60)
    seconds = (elapsesdTime - hours*3600 - minutes*60)
    print("Compute Time -> ", hours, 'hours', minutes, 'minutes', seconds, 'seconds')
    return statusName

def online(input):
    global startTime
    startTime = time.time()
    data = input
    print("\n+++++++++++++++++++++++++++++++++++++++++++++++++++\n")
    print(data)
    print("\n+++++++++++++++++++++++++++++++++++++++++++++++++++\n")
    init(data)
    print("Job submitted")
    modelError = prepareModel()
    if (len(modelError) > 0) :
        return modelError
    else:
        print("Solution requested")
        return solve()


def prepareModel():

    allocate()
    inSync()
    groupAddUp()
    teacherNoConflict()
    rommPreFill()


    postConstraints(constraints)

    roomNoConflict() # depends on constraints being posted

    postObjective()
    return model.Validate()

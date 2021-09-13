import pandas as pd
import re
import json
import math
import os
from school_tt import online

folder = os.getcwd() + "\\Input\\"
#folder = "I:\\XL_Timetable\\Input\\"


print('Execting from ... ', os.getcwd())
print("Looking for csv files in 'Input' folder in current working directory ")


data = {}

# # Load and Transform Structure data


print("Loaded Params.csv ...")

df_params = pd.read_csv(folder + 'Params.csv', header=None)


data['PERIODS_PER_DAY'] = int(df_params[1][0])
data['WEEK_LEN'] = int(df_params[1][1])
data['REPEAT'] = int(df_params[1][2])
data['RECESS_AFTER'] = int(df_params[1][3])


# # Load and Transform Master data

df_rooms = pd.read_csv(folder + 'Rooms.csv', index_col=['RID'])
df_rooms.dropna(how="all", inplace=True)
rooms = {}
print("Loaded Rooms.csv ...")

df_teachers = pd.read_csv(folder + 'Teachers.csv', index_col=['TID'])
df_teachers.dropna(how="all", inplace=True)
teachers = {}
print("Loaded Teachers.csv ...")

df_groups = pd.read_csv(folder + 'Classes.csv', index_col=['GID'])
df_groups.dropna(how="all", inplace=True)
groups = {}
print("Loaded Classes.csv ...")


def getRoomId(room_name):
    for id, V  in rooms.items():
        if room_name == V['name']:
            return id
    return  -1
def getTeacherId(teacher_name):
    for id, V  in teachers.items():
        if teacher_name == V['name']:
            return id
    return  -1
def getGroupId(group_name):
    for id, V  in groups.items():
        if group_name == V['name']:
            return id
    return  -1


room_types = {
    "Lecture": 100,
    "Special": 101
}

for row_index, row in df_rooms.iterrows():
    room = {
       "name": row['Name'],
       "type": room_types[row['Type']],
       "unavailability": [],

    }
    rooms[int(row_index)] = room

for row_index, row in df_teachers.iterrows():
    teacher = {
       "name": row['Name'],
       "unavailability": [],

    }
    teachers[int(row_index)] = teacher


for row_index, row in df_groups.iterrows():
    group = {
       "name": row['Name'],
       "classteacher": getTeacherId(row['Classteacher']),
       "classroom": getRoomId(row['Classroom']),
    }
    groups[int(row_index)] = group

# # Load and Transform Sessions Data


df_sessions = pd.read_csv(folder + 'protected.csv', index_col=['Session ID'])
df_sessions.dropna(how="all")
sessions = {}
print("Loaded Protected.csv  (Sessions Data) ...")


for row_index, row in df_sessions.iterrows():
    scope = row['GID'] if (type(row['GID']) == str) else str(row['GID'])
    session = {
        'elective_id': row['Elective ID'],
        'participating_groups': [int(i.strip()) for i in scope.split(",") if i.strip() != ''],
        'credits': row['Number of periods per cycle'],
        'teacher_id': row['TID'],
        'room_id': -1 if (row['RID'] == "" or math.isnan(row['RID'])) else int(row['RID']),
        'subject': row['Subject']
    }
    sessions[row_index] = session


instances = {}
eids = df_sessions['Elective ID'].unique()
eids.sort()
for iid in eids:
    first_found = False
    for _, session in sessions.items():
        if session['elective_id'] == iid:
            if iid in instances:
                instance = instances[iid]
                tsr = [session['teacher_id'], session['subject'], session['room_id']]
                instance['teacher_subject_room'].append(tsr)
                if (session['credits'] != instance['periods_per_cycle']):
                    print("WEIRD")
                if (session['participating_groups'] != instance['scope']):
                    print("WEIRD")

            else:
                instance = {'periods_per_cycle': session['credits'],
                          'scope': session['participating_groups'],
                          'teacher_subject_room': [[session['teacher_id'], session['subject'], session['room_id']]]
                         }
                instances[iid] = instance



print(sessions)

print(instances)


# # Load and Transform Constraints Data

constraints = []


df_classteacher = pd.read_csv(folder + 'Classteacher.csv')

for row_index, row in df_classteacher.iterrows():
    constraint = {
       "JSON_KEY_TYPE": row['Variant'],
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance'])
    }
    constraints.append(constraint)
print("Loaded Classteacher.csv ...")

df_classteacher = pd.read_csv(folder + 'Pin.csv')

for row_index, row in df_classteacher.iterrows():
    constraint = {
       "JSON_KEY_TYPE": "PIN_SESSION",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_ID": int(row['SessionID']),
       "JSON_KEY_ROOM_ID": getRoomId(row['Pinned Room'])
    }
    constraints.append(constraint)
print("Loaded Pin.csv ...")


df_classteacher = pd.read_csv(folder + 'Lecture.csv')

for row_index, row in df_classteacher.iterrows():
    ssids = row['Session IDs'] if type(row['Session IDs']) == str else str(row['Session IDs'])
    constraint = {
       "JSON_KEY_TYPE": "LECTURE_ONLY",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_IDS": [int(i.strip()) for i in ssids.split(',') if i.strip() != ""]
    }
    constraints.append(constraint)
print("Loaded Lecture.csv ...")


cumul_lookup = {
    "None": "NONE",
    "All": "ALL",
    "At most one": "AT_MOST",
    "At least one": "AT_LEAST",
    "Exactly one": "EXACTLY"
}

condition_lookup = {
    "Are on different Days": "IS_DD",
    "Are on different Halves": "IS_DH",
    "Are all continuous": "IS_AC"
}
slot_choices= {
    "Is First Period": "IS_FP",
    "Is Last Period": "IS_LP",
    "Is Just After Recess": "IS_JAL",
    "Is Just Before Recess": "IS_JBL"
}


df_classteacher = pd.read_csv(folder + 'Continuous.csv')

for row_index, row in df_classteacher.iterrows():
    ppos = row['Period Pos'] if type(row['Period Pos']) == str else str(row['Period Pos'])
    constraint = {
       "JSON_KEY_TYPE": "SESSION_INTERDEPENDENCE",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_CONDITION": condition_lookup[row['InterDependence']],
       "JSON_KEY_SESSION_ID": row['SessionID'],
       "JSON_KEY_PERIOD_POS": [int(i.strip()) for i in ppos.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded Continuous.csv ...")


df_classteacher = pd.read_csv(folder + 'TeacherAvailability.csv')

for row_index, row in df_classteacher.iterrows():
    unavailability = row['UnAvailability'] if type(row['UnAvailability']) == str else str(row['UnAvailability'])
    constraint = {
       "JSON_KEY_TYPE": "TEACHER_AVAILABILITY",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_TEACHER_ID": getTeacherId(row['Teacher']),
       "JSON_KEY_AVAILABILITY": [int(i.strip()) for i in unavailability.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded TeacherAvailability.csv ...")


df_classteacher = pd.read_csv(folder + 'RoomAvailability.csv')

for row_index, row in df_classteacher.iterrows():
    unavailability = row['UnAvailability'] if type(row['UnAvailability']) == str else str(row['UnAvailability'])
    constraint = {
       "JSON_KEY_TYPE": "ROOM_AVAILABILITY",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_ROOM_ID": getRoomId(row['Room']),
       "JSON_KEY_AVAILABILITY": [int(i.strip()) for i in unavailability.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded RoomAvailability.csv ...")


df_classteacher = pd.read_csv(folder + 'Timings.csv')

for row_index, row in df_classteacher.iterrows():
    ppos = row['Period Pos'] if type(row['Period Pos']) == str else str(row['Period Pos'])
    constraint = {
       "JSON_KEY_TYPE": "SESSION_DAYS",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_ID": row['SessionID'],
       "JSON_KEY_PERIOD_POS": [int(i.strip()) for i in ppos.split(",") if i.strip() != ''],
       "JSON_KEY_QUALIFIER": cumul_lookup[row['Qualifier']],
       "JSON_KEY_CONDITION": row['Day']
    }
    constraints.append(constraint)
print("Loaded Timings.csv ...")


df_classteacher = pd.read_csv(folder + 'Timings2.csv')

for row_index, row in df_classteacher.iterrows():
    ppos = row['Period Pos'] if type(row['Period Pos']) == str else str(row['Period Pos'])
    constraint = {
       "JSON_KEY_TYPE": "SESSION_TIMINGS",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_ID": row['SessionID'],
       "JSON_KEY_PERIOD_POS": [int(i.strip()) for i in ppos.split(",") if i.strip() != ''],
       "JSON_KEY_QUALIFIER": cumul_lookup[row['Qualifier']],
       "JSON_KEY_CONDITION": slot_choices[row['Condition']]
    }
    constraints.append(constraint)
print("Loaded Timings2.csv ...")


df_classteacher = pd.read_csv(folder + 'Suitability.csv')

for row_index, row in df_classteacher.iterrows():
    sids = row['Session IDs'] if type(row['Session IDs']) == str else str(row['Session IDs'])
    rids = row['Rooms'] if type(row['Rooms']) == str else str(row['Rooms'])

    constraint = {
       "JSON_KEY_TYPE": "ROOM_SUITABILITY",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_IDS": [int(i.strip()) for i in sids.split(",") if i.strip() != ''],
       "JSON_KEY_IS_SUITED": row['isSuitable'],
       "JSON_KEY_ROOM_IDS": [getRoomId(i.strip()) for i in rids.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded Suitability.csv ...")


df_classteacher = pd.read_csv(folder + 'Claim.csv')

for row_index, row in df_classteacher.iterrows():
    ppos = row['Period Pos'] if type(row['Period Pos']) == str else str(row['Period Pos'])
    constraint = {
       "JSON_KEY_TYPE": "ROOM_CLAIM",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
       "JSON_KEY_SESSION_ID": row['SessionID'],
       "JSON_KEY_ROOM_ID": getRoomId(row['Room']),
       "JSON_KEY_PERIOD_POS": [int(i.strip()) for i in ppos.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded Claim.csv ...")


df_classteacher = pd.read_csv(folder + 'Accessibility.csv')

for row_index, row in df_classteacher.iterrows():

    rids = row['Rooms'] if type(row['Rooms']) == str else str(row['Rooms'])

    constraint = {
       "JSON_KEY_TYPE": "TEACHER_ACCESSIBILITY",
       "JSON_KEY_IS_IGNORE": not row['Active'],
       "JSON_KEY_IS_HARD": row['Hard'],
       "JSON_KEY_IMPORTANCE": int(row['Importance']),
        "JSON_KEY_IS_ACCESSIBLE": row['isAccessible'],
        "JSON_KEY_TEACHER_ID": getTeacherId(row['Teacher']),
        "JSON_KEY_ROOM_IDS": [getRoomId(i.strip()) for i in rids.split(",") if i.strip() != '']
    }
    constraints.append(constraint)
print("Loaded Accessibility.csv ...")


data['teachers']=teachers
data['groups']=groups
data['rooms']=rooms
data['instances']=instances
data['sessions']=sessions
data['constraints']=constraints


# # Validation

# ### Uniqueness and Nulls

duplicates = df_rooms[df_rooms.duplicated(['Name'])]
if not duplicates.empty:
    print("Duplicates in Rooms " - duplicates)
duplicates = df_teachers[df_teachers.duplicated(['Name'])]
if not duplicates.empty:
    print("Duplicates in Teachers " - duplicates)
duplicates = df_groups[df_groups.duplicated(['Name'])]
if not duplicates.empty:
    print("Duplicates in classes" - duplicates)
duplicates = df_groups[df_groups.duplicated(['Classroom'])]
if not duplicates.empty:
    print("Duplicates in Classrooms " - duplicates)
duplicates = df_groups[df_groups.duplicated(['Classteacher'])]
if not duplicates.empty:
    print("Duplicates in Classteachers" - duplicates)


if df_rooms.isnull().values.any():
    print('Null found in rooms')
if df_teachers.isnull().values.any():
    print('Null found in teachers')
if df_groups.isnull().values.any():
    print('Null found in classes')


# ### Load
classteacher_load = {}
for gid, group in groups.items():
    gname = group['name']
    tid = group['classteacher']
    tname = teachers[tid]['name']
    rid = group['classroom']
    for iid, instance in instances.items():
        if (gid in instance['scope']) and (len(instance['scope']) == 1) and instance['teacher_subject_room'][0][0] == tid:
            credits = instance['periods_per_cycle']
            if tname in classteacher_load:
                classteacher_load[tname] = classteacher_load[tname] + instance['periods_per_cycle']
            else:
                classteacher_load[tname] = instance['periods_per_cycle']

room_load = {}
for rid in df_rooms.index:
    for sid, session in sessions.items():
        if rid == session['room_id']:
            room_name = rooms[rid]['name']
            if room_name in room_load:
                room_load[room_name] = room_load[room_name] + session['credits']
            else:
                room_load[room_name] = session['credits']

teacher_load = {}

for sid, session in sessions.items():
    if teachers[session['teacher_id']]['name'] in teacher_load:
        teacher_load[teachers[session['teacher_id']]['name']] = teacher_load[teachers[session['teacher_id']]['name']] + session['credits']
    else:
        teacher_load[teachers[session['teacher_id']]['name']] = session['credits']


group_load = {groups[gid]['name']:0 for gid in groups.keys()}

for gid in groups.keys():
    for iid, instance in instances.items():
        if gid in instance['scope']:
            group_load[groups[gid]['name']] = group_load[groups[gid]['name']] + instance['periods_per_cycle']

print("################################ VALIDATE INPUTS ###########################################################")
print()
print("Teacher Load", teacher_load)
print("Number of participating Teachers", len(teacher_load.keys()))
print("Total load on teachers", sum(teacher_load.values()))

print("ClassTeacher load", classteacher_load)
print("Number of participating Classteachers", len(classteacher_load.keys()))
print("ClassTeacher load", sum(classteacher_load.values()))

print("Room load", room_load)
print("Number of rooms involved", len(room_load.keys()))

print("Class load", group_load)
print("Number of classes", len(group_load.keys()))
print()
print("################################ VALIDATE INPUTS ###########################################################")

online(data)

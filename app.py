from flask import Flask,render_template, redirect, url_for, request, session, flash , Response
from flask_wtf import FlaskForm
from flask_wtf.file import FileRequired
from wtforms import StringField, PasswordField, SubmitField, RadioField, SelectField, TextAreaField, validators, FileField, DateField
from wtforms.validators import InputRequired, Length, Email, EqualTo, DataRequired
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from flask_bcrypt import Bcrypt
import secrets
import dropbox
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta, date


# Initializations:
app = Flask(__name__)
app.config['SECRET_KEY'] = "6E5E1BCBA69C47FE"

bcrypt = Bcrypt(app)

cred = credentials.Certificate('IOT_Proj_1\\key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

dbx = dropbox.Dropbox('<API KEY>')


# METHODS
#Send Email
def send_Email(userMail, userName, subject, body):
    try:
        mail = EmailMessage()
        mailEmail = 'iotgrp2023@gmail.com'
        mailPass = '<EMAIL PASS>'
        mail['From'] =  formataddr(("Vacancy Portal", mailEmail))
        mail['To'] =  formataddr((userName, userMail))
        mail['Subject'] = subject
        mail.set_content(body)


        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(mailEmail, mailPass)
            smtp.send_message(mail)

    except:
        flash('Error: Cannot Send Email','error')

#Increment ID for document in collection
def getLatestId(collection):
    colObj = db.collection(collection).stream()
    id = 0

    for doc in colObj:
        if int(doc.id) > id:
            id = int(doc.id)

    id+=1

    return id

#VALIDATION FUNCTIONS


def validate_dut4life_domain(form, emailField):
    dutDomain = "dut4life.ac.za"

    if not emailField.data.endswith('@'+dutDomain):
        raise validators.ValidationError("Invalid email, please use your Dut4life email")

def validate_dut_domain(form, emailField):
    dutDomain = "dut.ac.za"

    if not emailField.data.endswith('@'+dutDomain):
        raise validators.ValidationError("Invalid email, please use your Dut email")

def validate_studnumber(form, studnum):
    StudU = db.collection('Student').document(
        '{0}'.format(studnum.data))
    Stud = StudU.get()
    if Stud.exists:
        raise validators.ValidationError("This Student Number already exists.")

def validate_staffnumber(form, staffnum):
    LecturerU = db.collection('Lecturer').document(
        '{0}'.format(staffnum.data))
    lec = LecturerU.get()
    if lec.exists:
        raise validators.ValidationError("This Staff Number already exists.")

def validate_stud_email_exists(form, studEmail):
    StudU = db.collection('Student').where('email',"==",studEmail.data)
    if StudU.get():
        raise validators.ValidationError("This Student Email already exists.")

def validate_lec_email_exists(form, lecEmail):
    LecU = db.collection('Lecturer').where('email',"==",lecEmail.data)
    if LecU.get():
        raise validators.ValidationError("This Lecturer Email already exists.")

def check_weekday(date):
    return date.weekday() >= 5
# end of Methods

# VIEWS Section
@app.route("/", methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        UserType = request.form["UserType"]
        User = db.collection('{0}'.format(UserType)).document(
            '{0}'.format(form.number.data)).get()
        if User.exists:
            if bcrypt.check_password_hash(User.to_dict().get('password').decode('utf-8'),form.password.data):
                session["user"] = form.number.data
                session["type"] = UserType

                flash(f'Welcome, {User.to_dict().get("name")}.','success')

                return redirect(url_for("v_board"))

            else:
                flash("Incorrect Password", 'error')
        else:
            flash("Invalid Number",'error')
    else:
        if "user" in session:
            if session["type"] == "Student":
                return redirect(url_for("v_board"))
            else:
                return redirect(url_for("profile_lec"))

    return render_template("index.html", form=form)

@app.route("/forgot-pass", methods=['GET', 'POST'])
def forgot_pass():
    form = ForgotPass()

    if form.validate_on_submit():
        userType = request.form["UserType"]
        User = db.collection('{0}'.format(userType)).where("email","==",form.email.data).limit(1)
        dUser = User.get()

        if dUser:
            secretTok = secrets.token_urlsafe(16)

            UserDetails = dUser[0].to_dict()
            UserNum = dUser[0].id

            db.collection(userType).document(UserNum).update({'pass_token':secretTok})

            send_Email(UserDetails['email'],UserDetails['name'],'Vacancy Portal - Reset Password'
                       ,f"Hello, {UserDetails['name']}.\n\nTo reset your password, please go to http://iotproj1.pythonanywhere.com/reset-pass/{secretTok} \n\nThank you.\nKind regards,\nVacancy Team")

            flash('An email has been sent to you for you to reset your password','success')
        else:
            flash('This email does not exist','error')

    return render_template('forgot_pass.html',form=form)

@app.route("/reset-pass/<secretTok>", methods=['GET', 'POST'])
def reset_pass(secretTok):

    findStud = db.collection('Student').where('pass_token','==',secretTok).limit(1)
    findLec = db.collection('Lecturer').where('pass_token','==',secretTok).limit(1)

    getStud = findStud.get()
    getLec = findLec.get()

    userType = None
    docId = None

    if getStud:
        userType = 'Student'
        docId = getStud[0].id
    elif getLec:
        userType = 'Lecturer'
        docId = getLec[0].id
    else:
        return render_template("error.html")

    form = ResetPass()

    if (form.validate_on_submit()) and (userType is not None) and (docId is not None):

        hashed_password = bcrypt.generate_password_hash(form.newPas.data)
        db.collection(userType).document(docId).update({'password':hashed_password, 'pass_token':''})

        return render_template('password_changed.html')
    else:
        return render_template('reset_pass.html', form = form)

#change password
@app.route("/change-password", methods = ['GET','POST'])
def change_pass():
    if ("user" in session):
        form = ChangePass()
        if form.validate_on_submit():
            getUser= db.collection(session["type"]).document(session["user"])

            if bcrypt.check_password_hash(getUser.get().to_dict().get('password').decode('utf-8'), form.currentPas.data):
                hashed_password = bcrypt.generate_password_hash(form.newPas.data)
                getUser.update({'password':hashed_password})

                flash('Your password has been changed','success')
                if session["type"] == "Student":
                    return redirect(url_for('profile_stud'))
                else:
                    return redirect(url_for('profile_lec'))
            else:
                flash('Your current password is incorrect','error')

        return render_template('change_password.html', form = form)
    else:
        return redirect(url_for("login"))

@app.route("/signup-stud", methods=['GET', 'POST'])
def signup_stud():
    form = SignupStudForm()

    if form.validate_on_submit():

        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = db.collection('Student').document(
            '{0}'.format(form.number.data))
        new_user.set({
            'name' : form.name.data,
            'faculty' : form.faculty.data,
            'course' : form.course.data,
            'ID' : form.ID.data,
            'email' : form.email.data,
            'password': hashed_password,
            'pass_token':''
        })

        file = form.file.data

        dbx.files_upload(file.read(),f'/{form.number.data}/{form.number.data}.pdf')

        send_Email(form.email.data,form.name.data,"Welcome to DUT Vacancy Portal"
                   ,f"Welcome to DUT Vacancy Portal, {form.name.data}.\n\nYour account has been successfully created with us.\n\nThank you.\nKind regards,\nVancancy Team.")

        return redirect(url_for("login"))

    return render_template("signup_stud.html", form = form)

@app.route("/signup-lec", methods=['GET', 'POST'])
def signup_lec():
    form = SignupLecForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = db.collection('Lecturer').document(
            '{0}'.format(form.number.data))
        new_user.set({
            'name' : form.name.data,
            'faculty' : form.faculty.data,
            'email' : form.email.data,
            'password': hashed_password,
            'pass_token':''


        })

        send_Email(form.email.data,form.name.data,"Welcome to DUT Vacancy Portal"
                   ,f"Welcome to DUT Vacancy Portal, {form.name.data}.\n\nYour account has been successfully created with us.\n\nThank you.\nKind regards,\nVancancy Team.")

        return redirect(url_for("login"))

    return render_template("signup_lec.html", form = form)

@app.route("/profile-stud", methods=['GET', 'POST'])
def profile_stud():
    if ("user" in session) and (session["type"] == "Student"):
        form = ProfileStud()
        Student = db.collection('Student').document(
            '{0}'.format(session["user"]))
        dStudent = Student.get().to_dict()
        form.name.data = dStudent.get('name')
        form.number.data = session['user']
        form.faculty.data = dStudent.get('faculty')
        form.course.data = dStudent.get('course')
        form.ID.data = dStudent.get('ID')
        form.email.data = dStudent.get('email')

        form.currentpos.data = "Student"
        form.modules.data = ""

        Pos = db.collection('Tutor').document('{0}'.format(session["user"])).get()

        if Pos.exists:
            form.currentpos.data = Pos.to_dict().get('type')

            ModulesTut = db.collection('Module_Tutor').where('tutor_id',"==",session["user"])
            if ModulesTut.get():
                tempMod = ""

                for m in ModulesTut.stream():
                    if m.get('module') != None and m.get('module') not in tempMod:
                        tempMod += m.get('module') + "\n"

                form.modules.data = tempMod


        return render_template("profile_stud.html", form = form)
    else:
        return redirect(url_for("login"))

@app.route("/profile-lec", methods=['GET', 'POST'])
def profile_lec():
    if ("user" in session) and (session["type"] == "Lecturer"):
        form = ProfileLec()
        Lecturer = db.collection('Lecturer').document(
            '{0}'.format(session["user"]))
        dLecturer = Lecturer.get().to_dict()
        form.name.data = dLecturer.get('name')
        form.number.data = session['user']
        form.faculty.data = dLecturer.get('faculty')
        form.email.data = dLecturer.get('email')


        return render_template("profile_lec.html", form = form)
    else:
        return redirect(url_for("login"))

@app.route("/vacancy-board", methods = ['GET','POST'])
def v_board():
    if ("user" in session):
        listVac = []
        if session["type"] == "Student":
            vac = db.collection("Vacancy").where("status","==","1")
            appliedApp = db.collection("Application").where("student_num","==",session["user"])


            if vac.get():
                VacDoc = vac.stream()
                for doc in VacDoc:
                    exists = False
                    Lect = db.collection("Lecturer").document(doc.get('created_by'))
                    if appliedApp.get():
                        AppQuery = db.collection("Application").where("student_num","==",session["user"]).where('vacancy_id',"==",doc.id)
                        if AppQuery.get():
                            exists = True
                    if not exists:
                        VacDict = doc.to_dict()
                        VacDict.update({"lecturer":Lect.get().to_dict().get('name')})
                        VacDict.update({"vac_id":doc.id})
                        listVac.append(VacDict)
            return render_template("vacancy_board.html", obj = listVac)
        else:
            vac = db.collection("Vacancy").where("created_by","==",session["user"])

            vacDoc = vac.stream()

            for v in vacDoc:
                AppMade = db.collection("Application").where("vacancy_id","==",v.id).where("status","==","pending")
                count = 0
                if AppMade.get:
                    SApp = AppMade.stream()
                    for s in SApp:
                        count+=1

                Dict = v.to_dict()
                temp = ""
                match Dict.get('status'):
                    case '0': temp = "Complete"
                    case '1' : temp = "Available"
                    case '2' : temp = "Vacancy Withdrawn"

                Dict.update({"vac_id":v.id})
                Dict.update({"status_def":temp})
                Dict.update({"count":str(count)})
                listVac.append(Dict)

            return render_template("vacancy_board_lec.html", obj = listVac)


    else:
        return redirect(url_for("login"))

@app.route('/create-vacancy', methods=['GET','POST'])
def create_vac():
     if ("user" in session) and (session["type"] == "Lecturer"):
        form = CreateVac()

        if form.validate_on_submit():
            lateId = getLatestId('Vacancy')
            new_vac = db.collection('Vacancy').document('{0}'.format(str(lateId)))
            new_vac.set({
                'module' : form.module.data,
                'description' : form.description.data,
                'status' : '1',
                'type' : form.position_type.data,
                'created_by':session["user"]

            })

            flash('Vacancy Created','success')
            return redirect(url_for("v_board")) # Redirect to Vacancy board


        return render_template("c_vacancy.html", form = form)
     else:
        return redirect(url_for("login"))

@app.route('/application/<vac_id>', methods=['GET','POST'])
def create_application(vac_id):
     if ("user" in session) and (session["type"] == "Student"):

        lateId = getLatestId('Application')
        new_application = db.collection('Application').document('{0}'.format(str(lateId)))
        new_application.set({
            'status' : 'pending',
            'student_num':session["user"],
            'vacancy_id':vac_id
        })

        flash('Application created','success')
        return redirect(url_for("v_board")) # Redirect to Vacancy board
     else:
        return redirect(url_for("login")) # sort out views and links

#temp view app for lec page route
@app.route("/view-app-lec")
def view_app_lec():
    if ("user" in session) and (session["type"] == "Lecturer"):
        vac = db.collection("Vacancy").where("status","==","1").where("created_by","==",session["user"]).get()
        s_app = db.collection("Application").get()
        listVac = []

        for doc in vac:
            for appl in s_app:
                appDict = appl.to_dict()
                if (appDict.get('vacancy_id') == doc.id) and (appDict.get('status') == "pending"):
                    StudentCol = db.collection("Student").document(appDict.get('student_num')).get().to_dict()
                    Dict = doc.to_dict()
                    Dict.update({"doc_id": doc.id})
                    Dict.update(appDict)
                    Dict.update({"app_id":appl.id})
                    Dict.update({"name" : StudentCol.get('name')})
                    listVac.append(Dict)

        return render_template("temp_View_App_Lec.html", obj = listVac)
    else:
        return redirect(url_for("login"))

#Accept application by Lec -- NEED TO DOUBLE CHECK CODE
@app.route("/accept-app/<app_id>", methods =['GET','POST'])
def accept_app(app_id):
    if ("user" in session) and (session["type"] == "Lecturer"):

        getApp = db.collection("Application").document(str(app_id))
        getApp.update({"status":"accepted"})

        dictApp = getApp.get().to_dict()
        student_num = dictApp.get('student_num')


        getVac = db.collection("Vacancy").document(dictApp.get("vacancy_id"))
        getVac.update({"status" : "0"})

        dictVac = getVac.get().to_dict()

        getStudent = db.collection("Student").document(student_num).get().to_dict()
        student_name = getStudent.get("name")
        send_Email(getStudent.get("email"),student_name,"Vacancy Portal - Application Accepted"
                   ,f"Hello, {student_name}.\n\nYou have been accepted as a {dictVac.get('type')} for {dictVac.get('module')}.\n\nPlease contact the lecturer responsible for more information.\n\nThank you.\nKind regards,\nVacancy Team.")

        getTutor = db.collection("Tutor").document(student_num)
        lateId = getLatestId("Module_Tutor")
        getModTutor = db.collection("Module_Tutor").document(str(lateId))

        if not getTutor.get().exists:
            getTutor.set({
                "type" : dictVac.get("type")
            })
        elif  (getTutor.get().to_dict().get("type") != dictVac.get("type")) and (dictVac.get("type") == "Teaching Assistant"):
            getTutor.update({'type':dictVac.get("type")})


        getModTutor.set({
                'tutor_id' : student_num,
                'staff_num' : session["user"],
                'module' : dictVac.get("module")
            })

        otherApp = db.collection("Application").where("vacancy_id","==",dictApp.get("vacancy_id")).where('student_num',"!=",student_num)

        if otherApp.get():
            for a in otherApp.stream():
                a.reference.update({"status":"declined"})
                appDict = a.to_dict()
                getDecStud = db.collection('Student').document(appDict['student_num']).get().to_dict()
                send_Email(getDecStud.get("email"),getDecStud.get("name"),"Vacancy Portal - Application Declined"
                   ,f"Hello, {getDecStud.get('name')}.\n\nUnfortunately your application has been declined for {dictVac.get('module')}.\n\nPlease contact the lecturer responsible for more information.\n\nThank you.\nKind regards,\nVacancy Team.")

        flash('Application Accepted','success')
        return redirect(url_for("view_app_lec"))
    else:
        return redirect(url_for("login"))

#Decline APP - CHECK CODE
@app.route("/decline-app/<app_id>", methods =['GET','POST'])
def decline_app(app_id):
    if ("user" in session) and (session["type"] == "Lecturer"):

        getApp = db.collection("Application").document(str(app_id))
        getApp.update({"status":"declined"})

        getStudent = db.collection("Student").document(getApp.get().to_dict().get('student_num')).get().to_dict()

        getVac = db.collection("Vacancy").document(getApp.get().to_dict().get('vacancy_id')).get().to_dict()


        send_Email(getStudent.get("email"),getStudent.get("name"),"Vacancy Portal - Application Declined"
                   ,f"Hello, {getStudent.get('name')}.\n\nUnfortunately your application has been declined for {getVac.get('module')}.\n\nPlease contact the lecturer responsible for more information.\n\nThank you.\nKind regards,\nVacancy Team.")

        flash('Application declined','success')
        return redirect(url_for("view_app_lec"))
    else:
        return redirect(url_for("login"))

#View Application Status - Student
@app.route("/view-app", methods=['GET','POST'])
def view_app_status():
    if ("user" in session) and (session["type"] == "Student"):
        StudApp = db.collection("Application").where("student_num","==",session["user"])
        listStud = []

        if StudApp.get():
            dStudApp = StudApp.stream()
            for s in dStudApp:
                Dict = s.to_dict()
                VacDet = db.collection("Vacancy").document(Dict.get('vacancy_id')).get().to_dict()
                LecDet = db.collection("Lecturer").document(VacDet.get('created_by')).get().to_dict()
                Dict.update({"lec_name":LecDet.get("name")})
                Dict.update({'description':VacDet.get('description')})
                Dict.update({'module':VacDet.get('module')})
                Dict.update({'type':VacDet.get('type')})
                Dict.update({'app_id':s.id})
                listStud.append(Dict)

        return render_template("view_app.html", obj = listStud)

    else:
        return redirect(url_for("login"))

@app.route('/view-accepted-app')
def view_accepted_app():
    if ("user" in session) and (session["type"] == "Lecturer"):
        ApprovedVac = db.collection('Vacancy').where("status","==","0").where("created_by","==",session["user"])

        listObj = []

        if ApprovedVac.get():
            SApproved = ApprovedVac.stream()
            for a in SApproved:
                Dict = a.to_dict()
                Applications = db.collection("Application").where("vacancy_id","==",str(a.id)).where("status","==","accepted").limit(1)
                GetApp = Applications.get()

                if GetApp:
                    AppObj = GetApp[0].to_dict()
                    Student = db.collection('Student').document(AppObj.get('student_num')).get().to_dict()
                    Dict.update({"name":Student.get('name')})
                    Dict.update({"number":AppObj.get('student_num')})
                    listObj.append(Dict)

        return render_template('view_accepted_application.html', obj = listObj)

    else:
        return redirect(url_for("login"))


#Withdraw application if the application is pending
@app.route("/withdraw/<app_id>", methods=['GET','POST'])
def withdraw(app_id):
    if ("user" in session) and (session["type"] == "Student"):

        getApp = db.collection('Application').document(app_id)
        getApp.update({"status":"withdrawn"})

        flash('Application withdrawn','success')
        return redirect(url_for('view_app_status'))
    else:
        return redirect(url_for("login"))

@app.route("/withdraw-vac/<vac_id>", methods=['GET','POST'])
def withdraw_vac(vac_id):
    if ("user" in session) and (session["type"] == "Lecturer"):

        getVac = db.collection('Vacancy').document(vac_id)
        getVac.update({"status":"2"})

        getApp = db.collection("Application").where("vacancy_id","==",vac_id).where("status","not-in",["declined","withdrawn"])

        if getApp.get:
            sGetApp = getApp.stream()
            for a in sGetApp:
                a.reference.update({"status":"vacancy withdrawn"})

        flash('Vacancy withdrawn','success')

        return redirect(url_for('v_board'))
    else:
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.pop("user",None)
    session.pop("type",None)
    return redirect(url_for("login"))

@app.route("/download/<stud>", methods=['GET'])
def download(stud):
    if (not "user" in session):
        return render_template("error.html")

    if ((session["type"] == "Student") and (session["user"] != stud)):
        return render_template("error.html")

    path_on_dbx = f'/{stud}/{stud}.pdf'

    metadata, file = dbx.files_download(path_on_dbx)

    response  = Response(file)
    response.headers['Content-Disposition'] = f'attachment; filename={stud}.pdf'
    return response

@app.route("/update/<stud>", methods=['POST'])
def update(stud):
    if (not "user" in session):
        return render_template("error.html")

    if (session["user"] != stud):
        return render_template("error.html")

    if request.method=="POST":
        file = request.files['file']
        file_on_dpx = f'/{stud}/{stud}.pdf'

        with NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file)
            temp_file.close()

        with open(temp_file.name,'rb') as f:
            content = f.read()

        dbx.files_upload(content, file_on_dpx, mode=dropbox.files.WriteMode("overwrite"))

        flash('Your résumé has been updated','success')

    return redirect(url_for('profile_stud'))

#Appointments:
@app.route("/view-lec-appointment", methods = ['GET'])
def view_lec_appoint():
    if ("user" in session) and (session["type"] == "Lecturer"):
        Appointments = []

        getAppoint = db.collection("Appointment").where("staff_num","==",session["user"])

        if getAppoint.get:
            AppDoc = getAppoint.stream()

            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            for a in AppDoc:

                ADict = a.to_dict()
                start_time = datetime.strptime(ADict.get('start_time'),'%Y/%m/%d %H:%M')
                dt_str = start_time.strftime("%Y-%m-%d %H:%M")
                if dt_str > now:
                    getStudent = db.collection("Student").document(ADict.get('stud_num'))
                    StudDict = getStudent.get().to_dict()

                    ADict.update({'doc_id':a.id})
                    ADict.update({'app_date':start_time.strftime('%d/%m/%Y')})
                    ADict.update({'app_time':start_time.strftime('%H:%M')})
                    ADict.update({'stud_name':StudDict.get('name')})

                    Appointments.append(ADict)

        Appointments.sort(key=lambda x: x["start_time"],reverse=True)
        return render_template('view_appointment.html', obj = Appointments)

    else:
        return redirect(url_for('login'))

@app.route("/cancel-appoint/<id>")
def cancel_appoint(id):
    if ("user" in session):
        getAppoint = db.collection('Appointment').document(str(id))

        AppDict = getAppoint.get().to_dict()
        status_prior = AppDict.get('status')

        getAppoint.update({"status":"cancelled"})



        getStud = db.collection('Student').document(AppDict.get('stud_num')).get().to_dict()

        getLec = db.collection('Lecturer').document(AppDict.get('staff_num')).get().to_dict()

        start_time = datetime.strptime(AppDict.get('start_time'),'%Y/%m/%d %H:%M')

        if session["type"] == "Lecturer":
            send_Email(getStud.get("email"),getStud.get("name")
                       ,"Vacancy Portal - Appointment Cancelled"
                       ,f"Hello, {getStud.get('name')}.\n\nUnfortunately your appointment with {getLec.get('name')} on {start_time.strftime('%d/%m/%Y')} at {start_time.strftime('%H:%M')} has been cancelled.\n\nThank you.\nKind regards,\nVacancy Team.")
        else:
            if status_prior == "approved":
                stud_name = getStud.get('name')
                stud_num = AppDict.get('stud_num')
                lec_name = getLec.get("name")
                send_Email(getLec.get("email"),lec_name
                           ,f"Vacancy Portal - Appointment Cancelled with {stud_name}({stud_num})"
                           ,f"Hello, {lec_name}.\n\n{stud_name}({stud_num}) has cancelled their appointment with you that was scheduled for {start_time}.\n\nThank you.\nKind regards,\nVacancy Team.")


        flash('Appointment has been cancelled','success')

        if session["type"] == "Lecturer":
            return redirect(url_for('view_lec_appoint'))
        else:
            return redirect(url_for('view_stud_appoint'))

    return redirect(url_for('login'))

@app.route("/approve-appoint/<id>")
def approve_appoint(id):
    if ("user" in session):
        if (session["type"] == "Lecturer"):
            getAppoint = db.collection('Appointment').document(str(id))
            getAppoint.update({"status":"approved"})

            AppDict = getAppoint.get().to_dict()

            getStud = db.collection('Student').document(AppDict.get('stud_num')).get().to_dict()

            getLec = db.collection('Lecturer').document(AppDict.get('staff_num')).get().to_dict()

            start_time = datetime.strptime(AppDict.get('start_time'),'%Y/%m/%d %H:%M')

            send_Email(getStud.get("email"),getStud.get("name")
            ,"Vacancy Portal - Appointment Approved"
            ,f"Hello, {getStud.get('name')}.\n\nYour appointment with {getLec.get('name')} on {start_time.strftime('%d/%m/%Y')} at {start_time.strftime('%H:%M')} has been approved.\nPlease take note of the Date and Time of your appointment.\n\nThank you.\nKind regards,\nVacancy Team.")

            stud_num = AppDict.get("stud_num")

            otherAppoint = db.collection("Appointment").where("staff_num","==",session["user"]).where("start_time","==",AppDict.get("start_time"))

            if otherAppoint.get():
                for a in otherAppoint.stream():
                    ADict = a.to_dict()
                    if ADict.get('stud_num') != stud_num and ADict.get('status') == "pending":
                        a.reference.update({"status":"cancelled"})
                        getCStud = db.collection("Student").document(ADict.get("stud_num")).get().to_dict()
                        send_Email(getCStud.get("email"),getCStud.get("name")
                        ,"Vacancy Portal - Appointment Cancelled"
                        ,f"Hello, {getCStud.get('name')}.\n\nUnfortunately your appointment with {getLec.get('name')} on {start_time.strftime('%d/%m/%Y')} at {start_time.strftime('%H:%M')} has been cancelled.\n\nThank you.\nKind regards,\nVacancy Team.")



            flash('Appointment has been approved','success')

            return redirect(url_for('view_lec_appoint'))


    return redirect(url_for('login'))

@app.route("/view-stud-appointment", methods = ['GET'])
def view_stud_appoint():
    if ("user" in session) and (session["type"] == "Student"):
        Appointments = []

        getAppoint = db.collection("Appointment").where("stud_num","==",session["user"])

        if getAppoint.get:
            AppDoc = getAppoint.stream()

            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            for a in AppDoc:

                ADict = a.to_dict()
                start_time = datetime.strptime(ADict.get('start_time'),'%Y/%m/%d %H:%M')
                dt_str = start_time.strftime("%Y-%m-%d %H:%M")
                if dt_str > now:
                    getLecturer = db.collection("Lecturer").document(ADict.get('staff_num'))
                    LecDict = getLecturer.get().to_dict()
                    ADict.update({'doc_id':a.id})
                    ADict.update({'app_date':start_time.strftime('%d/%m/%Y')})
                    ADict.update({'app_time':start_time.strftime('%H:%M')})
                    ADict.update({'lec_name':LecDict.get('name')})
                    Appointments.append(ADict)

        Appointments.sort(key=lambda x: x["start_time"],reverse=True)
        return render_template('view_appointment_stud.html', obj = Appointments)

    else:
        return redirect(url_for('login'))

@app.route("/create-appointment",methods = ['GET', 'POST'])
def create_appointment():
    if ("user" in session) and (session["type"] == "Student"):

        form = CreateAppoint()

        getLec = db.collection('Lecturer').get()

        lecChoice = []

        for l in getLec:
            Dict = l.to_dict()
            lecChoice.append((l.id,Dict.get('name')))

        form.lecturer.choices = lecChoice

        today_date = date.today()
        minDate = today_date + timedelta(days=1)
        maxDate = today_date + timedelta(days=7)
        today_date = datetime.today()

        currentday = today_date.weekday()

        if currentday == 4:
            nextWeekDay = today_date + timedelta(days=3)
        elif currentday == 5:
            nextWeekDay = today_date + timedelta(days=2)
        else:
            nextWeekDay = today_date + timedelta(days=1)

        form.date_app.default = nextWeekDay.date()

        form.date_app.render_kw = {'min':minDate.strftime('%Y-%m-%d'),'max': maxDate.strftime('%Y-%m-%d')}


        if form.validate_on_submit():
            dateSelected = form.date_app.data
            if check_weekday(dateSelected):
                flash('Lecturer is unavailable on weekends','error')
            else:
                joinedDateTime = form.date_app.data.strftime('%Y/%m/%d') +' '+ form.time_app.data

                LecTakenAppoint = db.collection('Appointment').where("start_time","==",joinedDateTime).where("status","==","approved")

                if LecTakenAppoint.get():
                    flash('Chosen Date and Time is already taken. Please choose another Date and Time','error')
                else:
                    latestId = getLatestId('Appointment')
                    new_appointment = db.collection('Appointment').document('{0}'.format(str(latestId)))
                    new_appointment.set({
                        'staff_num' : form.lecturer.data,
                        'start_time' : joinedDateTime,
                        'status' : 'pending',
                        'stud_num' : session["user"]
                    })

                    getStud = db.collection('Student').document(session['user']).get().to_dict()

                    getLec = db.collection('Lecturer').document(form.lecturer.data).get().to_dict()

                    start_time = datetime.strptime(joinedDateTime,'%Y/%m/%d %H:%M')

                    send_Email(getStud.get("email"),getStud.get("name")
                    ,"Vacancy Portal - Appointment Submitted"
                    ,f"Hello, {getStud.get('name')}.\n\nYour appointment with {getLec.get('name')} on {start_time.strftime('%d/%m/%Y')} at {start_time.strftime('%H:%M')} has been submitted, and is waiting approval from the lecturer.\n\nThank you.\nKind regards,\nVacancy Team.")

                    flash('Appointment created successfully','success')

                    return redirect(url_for('view_stud_appoint'))



        form.process()
        return render_template('create_appoint.html', form=form)

    else:
        return redirect(url_for('login'))

# END OF VIEWS


# CLASSES Section:
#Login
class LoginForm(FlaskForm):
    number = StringField(validators=[InputRequired('Please enter your number'), Length(
        min=8, max=10)], render_kw={"placeholder": "Enter Student Number","onkeypress":"return isNumberKey(event);"})
    password = PasswordField(validators=[InputRequired('Please enter your password'), Length(
        min=6, max=20,message='Please ensure your password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Password"})
    submit = SubmitField("Login")

#Forgot Password
class ForgotPass(FlaskForm):
    email = StringField(validators=[InputRequired('Please enter your Student Email'),Email(message='Invalid Email'),Length(min=8,max=30,message="Invalid Email length")]
                         ,render_kw={"placeholder":"xxxxxxxx@dut4life.ac.za"})
    submit = SubmitField("Send Email")

#Reset Password
class ResetPass(FlaskForm):
    newPas = PasswordField(validators=[InputRequired('Please enter your New Password'), Length(
        min=6, max=20,message='Please ensure your new password is at least 6 characters and no more than 20 characters'), EqualTo('confirmpass', message='The passwords do not match')], render_kw={"placeholder": "Enter New Password"})
    confirmpass = PasswordField(validators=[InputRequired('Please repeat your New Password'), Length(
        min=6, max=20,message='Please ensure your repeat password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Repeat Password"})
    submit = SubmitField('Change Password')

#Signup for Student
class SignupStudForm(FlaskForm):
    name = StringField(validators=[InputRequired('Please enter your Name'),Length(min=5, max=30)]
                             ,render_kw={"placeholder":"Enter Name"})
    number = StringField(validators=[InputRequired('Please enter your Student Number'), Length(
        min=8, max=8,message='Please enter a valid Student Number'), validate_studnumber], render_kw={"placeholder": "Enter Student Number","onkeypress":"return isNumberKey(event);"})
    faculty = SelectField('Select your Faculty',choices=[('Faculty of Accounting & Informatics','Faculty of Accounting & Informatics')
                                                          ,('Faculty of Applied Sciences','Faculty of Applied Sciences')
                                                          ,('Faculty of Arts and Design','Faculty of Arts and Design')
                                                          ,('Faculty of Engineering and the Built Environment','Faculty of Engineering and the Built Environment')
                                                          ,('Faculty of Health Sciences','Faculty of Health Sciences')
                                                          ,('Faculty of Management Sciences','Faculty of Management Sciences')],validators=[InputRequired('Please select a Faculty')])
    course = StringField(validators=[InputRequired('Please enter your Course'),Length(min=5, max=100)]
                             ,render_kw={"placeholder":"Enter Course"})
    ID = StringField(validators=[InputRequired('Please enter your ID'), Length(min=13,max=13,message='Invalid ID number')]
                     ,render_kw={"placeholder":"Enter ID","onkeypress":"return isNumberKey(event);"})
    email = StringField(validators=[InputRequired('Please enter your Student Email'),Email(message='Invalid Email'),Length(min=23,max=23,message="Invalid Email length"), validate_dut4life_domain, validate_stud_email_exists]
                             ,render_kw={"placeholder":"xxxxxxxx@dut4life.ac.za"})
    password = PasswordField(validators=[InputRequired('Please enter your Password'), Length(
        min=6, max=20,message='Please ensure your password is at least 6 characters and no more than 20 characters'), EqualTo('confirmpass', message='The passwords do not match')], render_kw={"placeholder": "Enter Password"})
    confirmpass = PasswordField(validators=[InputRequired('Please repeat your Password'), Length(
        min=6, max=20,message='Please ensure your password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Repeat Password"})
    file = FileField('Résumé', validators=[FileRequired('Please upload your Résumé')],render_kw={"accept": ".pdf"})
    submit = SubmitField('Sign Up')

#Sign up for Lecturer
class SignupLecForm(FlaskForm):
    name = StringField(validators=[InputRequired('Please enter your Name'),Length(min=5, max=30)]
                             ,render_kw={"placeholder":"Enter Name"})
    number = StringField(validators=[InputRequired('Please enter your Staff Number'), Length(
        min=8, max=10,message='Please enter a valid Staff Number'), validate_staffnumber], render_kw={"placeholder": "Enter Staff Number"})
    faculty = SelectField('Select your Faculty',choices=[('Faculty of Accounting & Informatics','Faculty of Accounting & Informatics')
                                                          ,('Faculty of Applied Sciences','Faculty of Applied Sciences')
                                                          ,('Faculty of Arts and Design','Faculty of Arts and Design')
                                                          ,('Faculty of Engineering and the Built Environment','Faculty of Engineering and the Built Environment')
                                                          ,('Faculty of Health Sciences','Faculty of Health Sciences')
                                                          ,('Faculty of Management Sciences','Faculty of Management Sciences')],validators=[InputRequired('Please select a Faculty')])
    email = StringField(validators=[InputRequired('Please enter your Staff Email'),Email(message='Invalid Email'),Length(min=8,max=30,message="Invalid Email length"), validate_dut_domain, validate_lec_email_exists]
                             ,render_kw={"placeholder":"xxxxxxxx@dut.ac.za"})
    password = PasswordField(validators=[InputRequired('Please enter your Password'), Length(
        min=6, max=20,message='Please ensure your password is at least 6 characters and no more than 20 characters'), EqualTo('confirmpass', message='The passwords do not match')], render_kw={"placeholder": "Enter Password"})
    confirmpass = PasswordField(validators=[InputRequired('Please repeat your Password'), Length(
        min=6, max=20,message='Please ensure your password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Repeat Password"})

    submit = SubmitField('Sign Up')

#Profile for Student
class ProfileStud(FlaskForm):
    name = StringField(render_kw={"disabled":""})
    number = StringField(render_kw={"disabled":""})
    faculty = StringField(render_kw={"disabled":""})
    course = StringField(render_kw={"disabled":""})
    ID = StringField(render_kw={"disabled":""})
    email = StringField(render_kw={"disabled":""})
    currentpos = StringField(render_kw={"disabled":""})
    modules = TextAreaField(render_kw={"disabled":""})
    #submit = SubmitField('Update')

#Profile for Lecturer
class ProfileLec(FlaskForm):
    name = StringField(render_kw={"disabled":""})
    number = StringField(render_kw={"disabled":""})
    faculty = StringField(render_kw={"disabled":""})
    email = StringField(render_kw={"disabled":""})
    modules = TextAreaField(render_kw={"disabled":""}) #Should be editable
    submit = SubmitField('Update')

#Create Vacancy
class CreateVac(FlaskForm):
    module = StringField(validators=[InputRequired('Please enter the Module'),Length(min=7, max=7, message='The module name needs to be 7 characters long.')]
                             ,render_kw={"placeholder":"Enter Name"}) #Will change to a dropdown soon
    description = TextAreaField(validators=[InputRequired('Please enter a Description'),Length(min=0, max=300,message='The Description is too long.')]
                             ,render_kw={"placeholder":"Enter Description"})
    position_type = RadioField('Select the type of position:'
                              , choices=[('Tutor','Tutor'),('Teaching Assistant','Teaching Assistant')]
                              ,default = 'Tutor')
    submit = SubmitField('Create Vacancy')

#Change Password
class ChangePass(FlaskForm):
    currentPas = PasswordField(validators=[InputRequired('Please enter your Current Password'), Length(
        min=6, max=20,message='Please ensure your current password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Current Password"})
    newPas = PasswordField(validators=[InputRequired('Please enter your New Password'), Length(
        min=6, max=20,message='Please ensure your new password is at least 6 characters and no more than 20 characters'), EqualTo('confirmpass', message='The passwords do not match')], render_kw={"placeholder": "Enter New Password"})
    confirmpass = PasswordField(validators=[InputRequired('Please repeat your New Password'), Length(
        min=6, max=20,message='Please ensure your repeat password is at least 6 characters and no more than 20 characters')], render_kw={"placeholder": "Enter Repeat Password"})
    submit = SubmitField('Change Password')

#Create Appointment
class CreateAppoint(FlaskForm):
    lecturer = SelectField('Select Lecturer',validators=[InputRequired('Please select a Lecturer')],
                              validate_choice=False)
    date_app = DateField('Select Date',validators=[DataRequired('Please select a Date')], format='%Y-%m-%d')
    time_app = SelectField('Select Time',choices=[('09:00', '9:00 AM'), ('09:30', '9:30 AM'),
                ('10:00', '10:00 AM'), ('10:30', '10:30 AM'),
                ('11:00', '11:00 AM'), ('11:30', '11:30 AM'),
                ('12:00', '12:00 PM'), ('12:30', '12:30 PM'),
                ('13:00', '1:00 PM'), ('13:30', '1:30 PM'),
                ('14:00', '2:00 PM'), ('14:30', '2:30 PM'),
                ('15:00', '3:00 PM')],validators=[InputRequired('Please select a Time')],
                              validate_choice=False)
    submit = SubmitField('Create Appointment')


# END of CLASSES


if __name__ == '__main__':
    app.run()

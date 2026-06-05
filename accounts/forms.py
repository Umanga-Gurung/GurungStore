from django import forms
from app.models import Account, UserProfile


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control'
    }))
    first_name = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter First Name',
        'class': 'form-control',
    }))
    last_name = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter Last Name',
        'class': 'form-control'
    }))
    email = forms.CharField(widget=forms.EmailInput(attrs={
        'placeholder': 'Enter Email Address',
        'class': 'form-control',
    }))
    phone_number = forms.CharField(widget=forms.NumberInput(attrs={
        'placeholder': 'Enter Phone Number',
        'class': 'form-control'
    }))

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'password', 'confirm_password']

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(RegistrationForm, self).clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password != confirm_password:
            raise forms.ValidationError('password does not match')


class UserForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
    }))
    last_name = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': '',
        'class': 'form-control'
    }))
    phone_number = forms.CharField(widget=forms.NumberInput(attrs={
        'placeholder': '',
        'class': 'form-control'
    }))

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'phone_number']


POKHARA_LOCATIONS = [
    ('', 'Select your area in Pokhara...'),
    ('Lakeside (Baidam)', 'Lakeside (Baidam)'),
    ('Hallan Chowk', 'Hallan Chowk'),
    ('Khahare', 'Khahare'),
    ('Damside', 'Damside'),
    ('New Road', 'New Road'),
    ('Chipledhunga', 'Chipledhunga'),
    ('Mahendrapool', 'Mahendrapool'),
    ('Prithvi Chowk', 'Prithvi Chowk'),
    ('Srijana Chowk', 'Srijana Chowk'),
    ('Buddha Chowk', 'Buddha Chowk'),
    ('Zero KM', 'Zero KM'),
    ('Airport Area', 'Airport Area'),
    ('Bagar', 'Bagar'),
    ('Bindhyabasini', 'Bindhyabasini'),
    ('Miruwa', 'Miruwa'),
    ('Nadipur', 'Nadipur'),
    ('Ramghat', 'Ramghat'),
    ('Gairapatan', 'Gairapatan'),
    ('Malepatan', 'Malepatan'),
    ('Amarsingh', 'Amarsingh'),
    ('Rambazar', 'Rambazar'),
    ('Chauthe', 'Chauthe'),
    ('Birauta', 'Birauta'),
    ('Gharipatan', 'Gharipatan'),
    ('Chhorepatan', 'Chhorepatan'),
    ('Simpani', 'Simpani'),
    ('Masbar', 'Masbar'),
    ('Batulechaur', 'Batulechaur'),
    ('Lamachaur', 'Lamachaur'),
    ('Hemja', 'Hemja'),
    ('Sarangkot', 'Sarangkot'),
    ('Matepani', 'Matepani'),
    ('Kahun', 'Kahun'),
    ('Pumdi Bhumdi', 'Pumdi Bhumdi'),
    ('Pame', 'Pame'),
    ('Khapaudi', 'Khapaudi'),
    ('Phulbari (Fulbari)', 'Phulbari (Fulbari)'),
    ('Ranipauwa', 'Ranipauwa'),
    ('Parsyang', 'Parsyang'),
    ('Deep', 'Deep'),
    ('Miya Patan', 'Miya Patan'),
    ('Majheripatan', 'Majheripatan'),
    ('Shanti Patan', 'Shanti Patan'),
    ('Bagale Tole', 'Bagale Tole'),
    ('Fishtail Gate', 'Fishtail Gate'),
    ('Industrial Area', 'Industrial Area'),
]


class UserProfileForm(forms.ModelForm):
    address_line_1 = forms.ChoiceField(
        choices=POKHARA_LOCATIONS,
        widget=forms.Select(attrs={
            'class': 'form-select shadow-sm',
            'onfocus': "this.size=7; this.style.position='absolute'; this.style.zIndex='1050'; this.style.top='0'; this.style.left='0'; this.style.width='100%'; this.style.boxShadow='0 10px 25px rgba(0,0,0,0.15)'; this.style.borderRadius='8px';",
            'onchange': "this.size=1; this.style.position='static'; this.style.boxShadow='none'; this.blur();",
            'onblur': "this.size=1; this.style.position='static'; this.style.boxShadow='none';"
        })
    )
    address_line_2 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Street name or house no.', 'class': 'form-control'})
    )
    city = forms.CharField(
        initial='Pokhara',
        widget=forms.TextInput(attrs={'value': 'Pokhara', 'readonly': 'readonly', 'class': 'form-control bg-light'})
    )
    profile_pic = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = ['address_line_1', 'address_line_2', 'city', 'profile_pic']
